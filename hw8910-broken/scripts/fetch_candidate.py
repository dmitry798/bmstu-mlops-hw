"""Read-only MLflow import of the finished HW6+7 run (never trains/promotes)."""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('MLFLOW_HTTP_REQUEST_TIMEOUT','10')
os.environ.setdefault('MLFLOW_HTTP_REQUEST_MAX_RETRIES','1')
import mlflow
from mlflow import MlflowClient

p=argparse.ArgumentParser();p.add_argument('--tracking-uri',default='http://127.0.0.1:5006');p.add_argument('--workspace',type=Path,default=Path('.real'))
a=p.parse_args()
mlflow.set_tracking_uri(a.tracking_uri)
client=MlflowClient()
spec=json.loads((Path(__file__).resolve().parents[2]/'hw67-broken/docs/submission/candidate-model.json').read_text())
version=client.get_model_version(spec['name'],spec['version'])
if version.run_id != spec['run_id']:raise ValueError('Registry version/run mismatch')
run=client.get_run(spec['run_id'])
if run.info.status!='FINISHED':raise ValueError('Training run is unfinished')
print('READ EXISTING TRAINING RUN',run.info.run_id,flush=True)
a.workspace.mkdir(parents=True,exist_ok=True)
path=client.download_artifacts(spec['run_id'],'model',dst_path=str(a.workspace.resolve()))
print('ARTIFACT',path,flush=True)
