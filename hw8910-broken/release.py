"""Fail-closed release contracts; no ML dependencies."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

HASHES = ('model_sha256', 'protocol_sha256', 'golden_sha256', 'runtime_sha256')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def cache_key(data_path: Path, config: dict) -> str:
    return digest(canonical({'data_sha256': file_digest(data_path), 'config': config}))


def validate_release(manifest: dict, report: dict) -> None:
    try:
        if type(manifest['schema_version']) is not int or manifest['schema_version'] != 1:
            raise ValueError('Unsupported schema')
        for key in ('model_id', 'artifact_uri'):
            if not isinstance(manifest[key], str) or not manifest[key].strip():
                raise ValueError(f'Invalid {key}')
        for key in HASHES:
            if not isinstance(manifest[key], str) or not re.fullmatch('[0-9a-f]{64}', manifest[key]):
                raise ValueError(f'Invalid {key}')
        if not isinstance(manifest['runtime'], dict) or not manifest['runtime']:
            raise ValueError('Missing runtime')
        if digest(canonical(manifest['runtime'])) != manifest['runtime_sha256']:
            raise ValueError('Runtime hash mismatch')
        if report['status'] != 'complete' or report['passed'] is not True:
            raise ValueError('Incomplete or rejected evaluation')
        if not isinstance(report['evaluation_run_id'], str) or not report['evaluation_run_id'].strip():
            raise ValueError('Missing evaluation run')
        for key in ('model_id', *HASHES):
            if report[key] != manifest[key]:
                raise ValueError(f'Foreign report: {key}')
        for name in ('accuracy', 'format_rate'):
            value = report['metrics'][name]
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f'Invalid metric {name}')
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError(f'Invalid release schema: {exc}') from exc


def atomic_write(target, payload):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        # Persist directory entry as well as file contents.
        fd = os.open(target.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()


def publish(manifest: dict, report: dict, target: Path) -> None:
    validate_release(manifest, report)
    payload = canonical(manifest) + b'\n'
    if target.exists() and target.read_bytes() == payload: return
    atomic_write(target, payload)


def verify_files(manifest, workspace):
    """Artifact paths are pinned; remote registry resolution happens before this call."""
    files = manifest.get('file_hashes')
    if not isinstance(files, dict) or not files:
        raise ValueError('Missing artifact file inventory')
    base = Path(manifest.get('artifact_root', workspace)).resolve()
    if 'base_root' in manifest:
        for field,prefix in [('base_root','base'),('adapter_root','adapter')]:
            if Path(manifest[field]).resolve() != (base/prefix).resolve():
                raise ValueError(f'Loader path differs from verified inventory: {field}')
        if Path(manifest['tokenizer_root']).resolve() != Path(manifest['base_root']).resolve():
            raise ValueError('Tokenizer must use the pinned evaluated base snapshot')
    actual = {}
    for relative, expected in files.items():
        path = (base/relative).resolve()
        # HF snapshot files can be symlinks to shared blobs; inventory names must be safe.
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Unsafe artifact path')
        actual[relative] = file_digest(path)
        if actual[relative] != expected: raise ValueError(f'Artifact changed: {relative}')
    if digest(canonical(actual)) != manifest['model_sha256']:
        raise ValueError('Model inventory hash mismatch')


def release_id(manifest, report):
    return digest(canonical({'manifest': manifest, 'decision': report}))


def publish_event(manifest, report, root, fail_after_pointer=False):
    """One writer. Durable intent + atomic whole journal, replay before next attempt.

    No append window: crash after pointer replacement is repaired from pending.json.
    Identical releases keep one event, including rollback to a previously accepted ID.
    """
    root = Path(root)
    pending = root/'pending.json'
    journal = root/'publications.jsonl'
    def recover():
        if not pending.exists(): return
        intent = json.loads(pending.read_text())
        if intent.get('completed'): return
        m, r = intent['manifest'], intent['report']
        verify_files(m, root)
        publish(m, r, root/'accepted.json')
        events = [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
        if not any(e['release_id'] == intent['release_id'] for e in events):
            events.append({'release_id': intent['release_id'], 'model_id': m['model_id'], 'runtime_sha256': m['runtime_sha256'], 'evaluation_run_id': r['evaluation_run_id']})
            atomic_write(journal, b''.join(canonical(e)+b'\n' for e in events))
        atomic_write(pending, canonical({'completed': True, 'release_id': intent['release_id']}))
    recover()
    validate_release(manifest, report)
    verify_files(manifest, root)
    identity = release_id(manifest, report)
    atomic_write(pending, canonical({'manifest': manifest, 'report': report, 'release_id': identity}))
    publish(manifest, report, root/'accepted.json')
    if fail_after_pointer: raise RuntimeError('Injected crash after pointer before journal')
    recover()
    return identity
