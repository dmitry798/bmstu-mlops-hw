"""Generate explicit chart artifacts from pinned simulator manifests."""
from pathlib import Path
import hashlib,json,sys,yaml
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root.parent/'hw8910-broken'));import release
chart=root/'charts/hw11';templates=chart/'templates'
(chart/'Chart.yaml').write_text('apiVersion: v2\nname: hw11\nversion: 0.1.0\nappVersion: "1.0"\n')
(chart/'values.yaml').write_text('''image: hw11-api:1.1
modelVersion: A
warmupSeconds: 20
replicas: 2
brokenProbes: false
neverReady: false
maxRunning: 1
maxWaiting: 6
cacheCapacity: 8
cacheHitCPU: 0.015
cacheMissCPU: 0.14
chunkCPU: 0.01
''')
for version in ['A','B']:
    content=f'HW11 simulated CPU model version {version}\n';files={'model.txt':release.digest(content.encode())};runtime={'backend_mode':'simulated','version':version,'cache':'bounded cost-only LRU; no user responses'}
    manifest={'schema_version':1,'model_id':version,'artifact_uri':'configmap://hw11-model-'+version.lower(),'artifact_root':'/models','file_hashes':files,'model_sha256':release.digest(release.canonical(files)),'runtime':runtime,'runtime_sha256':release.digest(release.canonical(runtime)),'protocol_sha256':release.digest(b'hw11-ndjson-v1'),'golden_sha256':release.digest(b'simulator-no-quality-claim')}
    (templates/f'model-{version}.yaml').write_text(yaml.safe_dump({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'hw11-model-'+version.lower()},'immutable':True,'data':{'accepted.json':json.dumps(manifest),'model.txt':content}},sort_keys=False))
