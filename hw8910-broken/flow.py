"""Local Prefect release flow. Tasks exchange descriptors, never weights.

Preparation cache is persisted explicitly under workspace/cache, independently of
Prefect's orchestration database. It remains reusable across process restarts.
"""
import argparse
import json
import os
from pathlib import Path
import time
import uuid

os.environ.setdefault('PREFECT_HOME', str(Path(__file__).parent/'.prefect'))
os.environ.setdefault('PREFECT_SERVER_ANALYTICS_ENABLED', 'false')
from prefect import flow, task
from prefect.cache_policies import NO_CACHE
import lab
import release

def preparation_key(context, parameters):
    root = Path(parameters['workspace'])
    return release.digest(release.canonical({'workspace':str(root.resolve()), 'input':release.cache_key(root/'input.txt',lab.read(root/'config.json'))}))

@task(cache_key_fn=preparation_key, persist_result=True)
def prepare_input(workspace):
    root = Path(workspace)
    result = lab.prepare(root)
    return {'uri':str(root/'input.txt'), 'input_sha256':result['input_sha256'], 'rows':result['rows']}

@task(cache_policy=NO_CACHE)
def obtain_artifact(workspace, manifest_name):
    """Reads an existing training run artifact; does NOT retrain."""
    root = Path(workspace)
    manifest = lab.read(root/manifest_name)
    release.verify_files(manifest, root)
    return {'manifest_uri':str(root/manifest_name), 'model_id':manifest['model_id'], 'model_sha256':manifest['model_sha256']}

@task(cache_policy=NO_CACHE)
def evaluate_admission(workspace, artifact, report_name, prepared):
    root = Path(workspace)
    manifest = lab.read(artifact['manifest_uri'])
    report = lab.read(root/report_name)
    if not (manifest.get('synthetic') is True and report.get('synthetic') is True):
        from real_release import verify_bound_report, rows
        if release.file_digest(prepared['uri']) != prepared['input_sha256']:
            raise ValueError('Input changed after preparation')
        if release.digest(json.dumps(rows(prepared['uri']),ensure_ascii=False,sort_keys=True,allow_nan=False).encode()) != manifest['golden_sha256']:
            raise ValueError('Prepared golden differs from evaluated golden; repeat evaluation')
        verify_bound_report(manifest, report)
    release.validate_release(manifest, report)
    return {'report_uri':str(root/report_name), 'evaluation_run_id':report['evaluation_run_id']}

@task(cache_policy=NO_CACHE)
def publish_accepted(workspace, artifact, decision, fail_after_pointer):
    return release.publish_event(lab.read(artifact['manifest_uri']), lab.read(decision['report_uri']), Path(workspace), fail_after_pointer)

@flow(name='model-release', log_prints=True, retries=0)
def release_flow(workspace, manifest_name='manifest-B.json', report_name='report-B.json', fail_after_prepare=False, fail_after_pointer=False):
    root = Path(workspace)
    attempt = str(uuid.uuid4())
    outcome = {'attempt_id':attempt, 'started':time.time()}
    try:
        prepared = prepare_input(str(root))
        print('PREPARATION_DESCRIPTOR', json.dumps(prepared))
        if fail_after_prepare: raise RuntimeError('Injected failure after preparation')
        artifact = obtain_artifact(str(root), manifest_name)
        decision = evaluate_admission(str(root), artifact, report_name, prepared)
        identity = publish_accepted(str(root), artifact, decision, fail_after_pointer)
        outcome.update(status='complete', release_id=identity)
        return identity
    except Exception as exc:
        outcome.update(status='failed', error=str(exc))
        raise
    finally:
        with (root/'flow-attempts.jsonl').open('a') as stream:
            stream.write(json.dumps(outcome)+'\n')

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--workspace', type=Path, default=Path('.lab'))
    p.add_argument('--manifest', default='manifest-B.json')
    p.add_argument('--report', default='report-B.json')
    p.add_argument('--fail-after-prepare', action='store_true')
    p.add_argument('--fail-after-pointer', action='store_true')
    a = p.parse_args()
    release_flow(str(a.workspace.resolve()), a.manifest, a.report, a.fail_after_prepare, a.fail_after_pointer)
