"""HW6+7 provenance and fail-closed gate wrapper. No synthetic metric substitution.

The original baseline is an initial fallback, NOT a newly quality-approved release.
Candidate rejection is preserved even when the fallback itself performs poorly.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
import uuid
import release

PROJECT = Path(__file__).resolve().parent
PREVIOUS = PROJECT.parent/'hw67-broken'
spec = importlib.util.spec_from_file_location('hw67_solution', PREVIOUS/'evaluation/solution.py')
solution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(solution)


def read(path): return json.loads(Path(path).read_text())
def save(path, value): release.atomic_write(Path(path), release.canonical(value)+b'\n')
def rows(path): return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def require_protocol(manifest):
    config=read(PREVIOUS/'evaluation/params.json')
    protocol=dict(config=config,golden=rows(PREVIOUS/config['golden']),behavioral=rows(PREVIOUS/config['behavioral']),training_index=rows(PREVIOUS/config['training_index']),evaluation_code={p.name:p.read_text() for p in sorted((PREVIOUS/'evaluation').glob('*.py'))})
    fingerprint=release.digest(json.dumps(protocol,ensure_ascii=False,sort_keys=True,allow_nan=False).encode())
    if fingerprint!=manifest['protocol_sha256']:raise ValueError('Protocol changed; create a new bound manifest and repeat evaluation')
    generation=manifest['runtime']['generation']
    if any(generation[key]!=config[key] for key in ['system','seed','max_new_tokens','enable_thinking']):
        raise ValueError('Runtime generation differs from evaluation protocol')
    return config


def source_record(path):
    path = Path(path).resolve()
    return {'uri':str(path), 'sha256':release.file_digest(path)}


def previous_gate(destination):
    """Re-score full saved real outputs and invoke the unmodified HW6+7 gate."""
    source = PREVIOUS/'docs/submission'
    config = read(PREVIOUS/'evaluation/params.json')
    golden = rows(PREVIOUS/config['golden'])
    behavior = rows(PREVIOUS/config['behavioral'])
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location('hw67_contract', PREVIOUS/'evaluation/contract.py')
    contract = module_from_spec(spec); spec.loader.exec_module(contract)
    reports = {}
    paths = [PREVIOUS/'evaluation/solution.py', PREVIOUS/'evaluation/params.json', PREVIOUS/config['golden'], PREVIOUS/config['behavioral'], PREVIOUS/'evaluation/baseline.json']
    for role in ['baseline', 'candidate']:
        report_path, output_path = source/f'{role}-eval.json', source/f'{role}-outputs.json'
        report, outputs = read(report_path), read(output_path)
        by_id = {o['id']:o for o in outputs}
        if len(by_id) != len(outputs): raise ValueError('Duplicate raw output IDs')
        rescored = solution.score(golden, [by_id[r['id']] for r in golden])
        rescored_behavior = solution.score(behavior, [by_id[r['id']] for r in behavior])
        for key in ['overall','slices','per_item']:
            if report[key] != rescored[key]: raise ValueError(f'Saved {role} evaluation does not match raw outputs: {key}')
        if rescored_behavior != report['behavioral']: raise ValueError('Behavioral output mismatch')
        if report['outputs_sha256'] != contract.fingerprint(outputs): raise ValueError('Outputs hash mismatch')
        if report['golden_sha256'] != contract.fingerprint(golden): raise ValueError('Golden hash mismatch')
        protocol=dict(config=config,golden=golden,behavioral=behavior,training_index=rows(PREVIOUS/config['training_index']),evaluation_code={p.name:p.read_text() for p in sorted((PREVIOUS/'evaluation').glob('*.py'))})
        if report['protocol_sha256'] != contract.fingerprint(protocol):raise ValueError('Saved evaluation protocol differs from current data/code/config')
        reports[role] = report
        paths.extend([report_path, output_path])
    decision = {'status':'complete','evaluation_run_id':reports['candidate']['evaluation_run_id'], 'training_run_id':reports['candidate']['model']['run_id'], 'critical_slices':config['critical_slices'], 'source_files':[source_record(p) for p in paths]}
    try:
        decision.update(solution.quality_gate(reports['baseline'], reports['candidate'], config['critical_slices']))
    except ValueError as exc:
        decision.update(passed=False, reason=str(exc))
    save(destination, decision)
    return reports, decision


def verify_bound_report(manifest, report):
    sources = report.get('source_files')
    if not sources: raise ValueError('No full evaluation source files')
    for item in sources:
        if release.file_digest(item['uri']) != item['sha256']: raise ValueError('Evaluation source changed')
    if report.get('acceptance_policy') == 'existing-baseline-fallback':
        raise ValueError('Baseline fallback is not a candidate PASS')
    config=require_protocol(manifest)
    if report['critical_slices']!=config['critical_slices']:raise ValueError('Critical slices changed')
    # A saved passed flag never substitutes for executing the original rule.
    paths = {Path(s['uri']).name:s['uri'] for s in sources}
    baseline = read(paths.get('baseline-runtime-eval.json', paths.get('baseline-eval.json')))
    candidate = read(paths.get('candidate-runtime-eval.json', paths.get('candidate-eval.json')))
    required={'baseline-runtime-outputs.json','candidate-runtime-outputs.json','golden.jsonl','behavioral.jsonl'}
    if not required <= paths.keys():raise ValueError('Missing raw evaluation source')
    golden=rows(paths['golden.jsonl']);behavior=rows(paths['behavioral.jsonl'])
    for role,evaluation in [('baseline',baseline),('candidate',candidate)]:
        outputs=read(paths[f'{role}-runtime-outputs.json'])
        by_id={o['id']:o for o in outputs}
        if len(by_id)!=len(outputs) or release.digest(release.canonical(outputs))!=evaluation['outputs_sha256']:raise ValueError('Raw output identity mismatch')
        rescored=solution.score(golden,[by_id[r['id']] for r in golden])
        for key in ['overall','slices','per_item']:
            if evaluation[key]!=rescored[key]:raise ValueError('Evaluation/raw output mismatch')
        if evaluation['behavioral']!=solution.score(behavior,[by_id[r['id']] for r in behavior]):raise ValueError('Behavioral mismatch')
    if baseline['runtime_sha256']!=candidate['runtime_sha256']:raise ValueError('Evaluation runtimes differ')
    if candidate.get('model_sha256') != manifest['model_sha256']:
        raise ValueError('Candidate weight identity mismatch')
    decision = solution.quality_gate(baseline, candidate, report['critical_slices'])
    if decision['passed'] is not True or report['passed'] is not True: raise ValueError('Gate rejected')
    if candidate['model']['run_id'] != manifest.get('training_run_id'): raise ValueError('Foreign training run')
    if candidate['protocol_sha256'] != manifest['protocol_sha256']: raise ValueError('Foreign protocol')
    # New candidate reports must include an explicit runtime binding, not infer it.
    if candidate.get('runtime_sha256') != manifest['runtime_sha256']: raise ValueError('Old evaluation has no proven runtime binding; re-evaluate')


def initialize(root, snapshot):
    root = Path(root).resolve()
    if root.exists(): raise FileExistsError('Use a new real workspace')
    root.mkdir(parents=True)
    reports, decision = previous_gate(root/'candidate-historical-gate.json')
    snapshot = Path(snapshot).absolute()
    baseline = read(PREVIOUS/'evaluation/baseline.json')
    if snapshot.name != baseline['revision']: raise ValueError('Snapshot revision differs from pinned baseline')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    config = read(PREVIOUS/'evaluation/params.json')
    files = {p.name:release.file_digest(p) for p in sorted(snapshot.iterdir()) if p.is_file()}
    tokenizer_files = {n:h for n,h in files.items() if n in ['tokenizer.json','tokenizer_config.json','vocab.json','merges.txt']}
    runtime = {'base_model':baseline['name'], 'base_revision':baseline['revision'],
               'tokenizer_sha256':release.digest(release.canonical(tokenizer_files)),
               'template_sha256':release.digest(tokenizer.chat_template.encode()),
               'generation':{'system':config['system'],'seed':config['seed'],'do_sample':False,'max_new_tokens':config['max_new_tokens'],'enable_thinking':config['enable_thinking']},
               'dtype':'bfloat16','device':'cpu','max_input_tokens':2048,
               'libraries':{'torch':'2.14.0','transformers':'5.17.0'}}
    manifest = {'schema_version':1,'model_id':f"baseline-Qwen3-0.6B-{baseline['revision'][:12]}",
                'artifact_uri':str(snapshot),'artifact_root':str(snapshot),'file_hashes':files,
                'model_sha256':release.digest(release.canonical(files)),
                'protocol_sha256':reports['baseline']['protocol_sha256'], 'golden_sha256':reports['baseline']['golden_sha256'],
                'runtime':runtime,'runtime_sha256':release.digest(release.canonical(runtime)),
                'acceptance_policy':'existing-baseline-fallback', 'baseline_spec':baseline,
                'previous_evaluation_run_id':reports['baseline']['evaluation_run_id']}
    release.verify_files(manifest, root)
    save(root/'manifest-baseline.json', manifest)
    save(root/'accepted.json', manifest)
    save(root/'baseline-origin.json', {'policy':'existing-baseline-fallback','new_candidate_pass':False,'reason':decision.get('reason'),'source_files':decision['source_files'], 'warning':'Baseline also fails behavioral tests; retained as prior fixed baseline, not promoted as quality PASS.'})
    (root/'input.txt').write_bytes((PREVIOUS/config['golden']).read_bytes())
    save(root/'config.json', {'data_format':'golden-jsonl','tokenizer_revision':baseline['revision'], 'tokenizer_sha256':runtime['tokenizer_sha256'], 'template_sha256':runtime['template_sha256'], 'max_length':2048,'code_revision':release.file_digest(PROJECT/'lab.py')})
    print('REAL BASELINE INITIALIZED', root, 'candidate gate:', decision['passed'], decision.get('reason'))


def evaluate_baseline(root, role="baseline"):
    """Full fresh baseline evaluation under EXACT serving runtime; no new training."""
    from service_core import TransformersBackend
    root = Path(root)
    manifest = read(root/('accepted.json' if role=='baseline' else 'manifest-candidate.json'))
    release.verify_files(manifest, root)
    backend = TransformersBackend(manifest)
    config = require_protocol(manifest)
    golden, behavior = rows(PREVIOUS/config['golden']), rows(PREVIOUS/config['behavioral'])
    golden_hash=release.digest(json.dumps(golden,ensure_ascii=False,sort_keys=True,allow_nan=False).encode())
    if golden_hash!=manifest['golden_sha256']:raise ValueError('Golden changed; create a new bound manifest before evaluation')
    outputs = []
    for row in golden+behavior:
        start = time.perf_counter()
        result, error = {}, None
        try: result = backend.generate(row['input'], manifest['runtime']['generation']['max_new_tokens'])
        except Exception as exc: error = f'{type(exc).__name__}: {exc}'
        outputs.append({'id':row['id'],'raw':result.get('answer',''),'error':error,'output_tokens':result.get('output_tokens',0),'latency_seconds':time.perf_counter()-start})
        print('REAL_EVAL',row['id'],outputs[-1]['output_tokens'],error, flush=True)
    by_id = {o['id']:o for o in outputs}
    result = solution.score(golden, [by_id[r['id']] for r in golden])
    result.update(status='complete',model=manifest.get('model_spec',manifest['baseline_spec']), model_sha256=manifest['model_sha256'], model_id=manifest['model_id'], runtime_sha256=manifest['runtime_sha256'], evaluation_run_id='hw8910-'+role+'-'+str(uuid.uuid4()), behavioral=solution.score(behavior,[by_id[r['id']] for r in behavior]), protocol_sha256=manifest['protocol_sha256'], golden_sha256=manifest['golden_sha256'], baseline_spec_sha256=release.digest(release.canonical(manifest['baseline_spec'])), outputs_sha256=release.digest(release.canonical(outputs)), acceptance_policy=manifest['acceptance_policy'])
    save(root/f'{role}-runtime-outputs.json', outputs)
    save(root/f'{role}-runtime-eval.json', result)
    print(role.upper()+'_METRICS',result['overall'],result['behavioral']['overall'])
    return result

def initialize_candidate(root):
    root = Path(root).resolve()
    baseline = read(root/'accepted.json')
    adapter = root/'model/artifacts/adapter'
    source_manifest = read(adapter/'manifest.json')
    if source_manifest['model']['revision'] != baseline['runtime']['base_revision']:
        raise ValueError('Adapter base differs from baseline')
    inventory = root/'candidate-artifact'
    inventory.mkdir(exist_ok=True)
    for name, target in [('base',Path(baseline['artifact_root'])),('adapter',adapter)]:
        link=inventory/name
        if not link.exists():link.symlink_to(target, target_is_directory=True)
    files={}
    for prefix,directory in [('base',Path(baseline['artifact_root'])),('adapter',adapter)]:
        for path in sorted(directory.rglob('*')):
            if path.is_file(): files[str(Path(prefix)/path.relative_to(directory))]=release.file_digest(path)
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(adapter,local_files_only=True)
    runtime=dict(baseline['runtime'])
    if release.digest(tokenizer.chat_template.encode()) != runtime['template_sha256']:
        raise ValueError('Adapter chat template is incompatible')
    # Use the same pinned base tokenizer bytes for both evaluated models and API.
    model_spec=read(PREVIOUS/'docs/submission/candidate-model.json')
    import yaml
    if yaml.safe_load((root/'model/MLmodel').read_text())['run_id']!=model_spec['run_id']:
        raise ValueError('Imported artifact belongs to another training run')
    manifest={**baseline,'model_id':'candidate-'+model_spec['run_id'], 'artifact_uri':model_spec['uri'],
              'artifact_root':str(inventory),'base_root':baseline['artifact_root'],'adapter_root':str(adapter),
              'tokenizer_root':baseline['artifact_root'],'file_hashes':files,'model_sha256':release.digest(release.canonical(files)),
              'runtime':runtime,'runtime_sha256':release.digest(release.canonical(runtime)),
              'training_run_id':model_spec['run_id'],'model_spec':model_spec,'acceptance_policy':'quality-gate-required'}
    release.verify_files(manifest,root)
    save(root/'manifest-candidate.json',manifest)
    print('EXISTING TRAINING ARTIFACT',model_spec['run_id'],'no retraining')


def current_gate(root):
    root=Path(root)
    baseline=read(root/'baseline-runtime-eval.json')
    candidate=read(root/'candidate-runtime-eval.json')
    manifest=read(root/'manifest-candidate.json')
    config=require_protocol(manifest)
    if baseline['runtime_sha256'] != candidate['runtime_sha256']:
        raise ValueError('Baseline and candidate runtime differ; repeat both under one protocol')
    golden=rows(PREVIOUS/config['golden']); behavior=rows(PREVIOUS/config['behavioral'])
    for role,evaluation in [('baseline',baseline),('candidate',candidate)]:
        outputs=read(root/f'{role}-runtime-outputs.json')
        by_id={o['id']:o for o in outputs}
        if len(by_id)!=len(outputs) or evaluation['outputs_sha256']!=release.digest(release.canonical(outputs)):
            raise ValueError('Raw output identity mismatch')
        actual=solution.score(golden,[by_id[r['id']] for r in golden])
        for key in ['overall','slices','per_item']:
            if evaluation[key]!=actual[key]:raise ValueError('Saved evaluation differs from raw outputs')
        if evaluation['behavioral']!=solution.score(behavior,[by_id[r['id']] for r in behavior]):raise ValueError('Behavioral output mismatch')
    if candidate['model_sha256']!=manifest['model_sha256'] or candidate['runtime_sha256']!=manifest['runtime_sha256']:
        raise ValueError('Candidate weights or runtime differ from evaluated version')
    report={key:manifest[key] for key in ['model_id',*release.HASHES]}
    report.update(status='complete',evaluation_run_id=candidate['evaluation_run_id'],
                  metrics={key:candidate['overall'][key] for key in ['accuracy','format_rate']},
                  critical_slices=config['critical_slices'],training_run_id=manifest['training_run_id'],
                  source_files=[source_record(path) for path in [root/'baseline-runtime-eval.json',root/'candidate-runtime-eval.json',root/'baseline-runtime-outputs.json',root/'candidate-runtime-outputs.json',PREVIOUS/'evaluation/solution.py',PREVIOUS/'evaluation/params.json',PREVIOUS/config['golden'],PREVIOUS/config['behavioral']]])
    try:report.update(solution.quality_gate(baseline,candidate,config['critical_slices']))
    except ValueError as exc:report.update(passed=False,reason=str(exc))
    save(root/'release-report.json',report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['init','evaluate','gate','candidate-init','candidate-evaluate','current-gate'])
    p.add_argument('--workspace',type=Path,default=PROJECT/'.real')
    p.add_argument('--snapshot',type=Path,default=Path.home()/'.cache/huggingface/hub/models--Qwen--Qwen3-0.6B/snapshots/c1899de289a04d12100db370d81485cdf75e47ca')
    a=p.parse_args()
    if a.command=='init': initialize(a.workspace,a.snapshot)
    elif a.command=='evaluate': evaluate_baseline(a.workspace)
    elif a.command=='candidate-init': initialize_candidate(a.workspace)
    elif a.command=='candidate-evaluate': evaluate_baseline(a.workspace,'candidate')
    elif a.command=='current-gate':
        report=current_gate(a.workspace);print(json.dumps(report,ensure_ascii=False,indent=2));sys.exit(0 if report['passed'] else 1)
    else:
        _, decision = previous_gate(a.workspace/'candidate-historical-gate.json')
        print(json.dumps(decision,ensure_ascii=False,indent=2))
        sys.exit(0 if decision['passed'] else 1)
