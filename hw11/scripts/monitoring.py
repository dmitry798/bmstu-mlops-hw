from pathlib import Path
import json,yaml
root=Path(__file__).resolve().parents[1]
objects=[]
def add(x):objects.append(x)
add({'apiVersion':'v1','kind':'ServiceAccount','metadata':{'name':'hw11-monitor','namespace':'hw11'}})
add({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'ClusterRole','metadata':{'name':'hw11-monitor'},'rules':[{'apiGroups':['','apps','autoscaling','discovery.k8s.io'],'resources':['nodes','nodes/proxy','nodes/metrics','pods','services','endpoints','namespaces','deployments','replicasets','horizontalpodautoscalers','endpointslices'],'verbs':['get','list','watch']}]})
add({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'ClusterRoleBinding','metadata':{'name':'hw11-monitor'},'subjects':[{'kind':'ServiceAccount','name':'hw11-monitor','namespace':'hw11'}],'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'hw11-monitor'}})
add({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'hw11-prometheus'},'data':{n:(root/'monitoring'/n).read_text() for n in ['prometheus.yaml','alerts.yaml']}})
panels=[]
queries=[('TTFC p95 (s)','histogram_quantile(0.95, sum by (le,pod) (rate(hw11_ttfc_seconds_bucket[30s])))','s'),('Total p95 (s)','histogram_quantile(0.95, sum by (le,pod) (rate(hw11_duration_seconds_bucket[30s])))','s'),('Running / waiting','{__name__=~"hw11_running|hw11_waiting"}','short'),('Terminal RPS','sum by(pod,outcome)(rate(hw11_requests_total[30s]))','reqps'),('CPU cores','sum by(pod)(rate(container_cpu_usage_seconds_total{namespace="hw11",container="api"}[30s]))','cores'),('Memory bytes','sum by(pod)(container_memory_working_set_bytes{namespace="hw11",container="api"})','bytes'),('Ready replicas','sum(kube_pod_status_ready{namespace="hw11",condition="true",pod=~"hw11-api-.*"})','short'),('Rejected / errors fraction','sum by(outcome)(rate(hw11_requests_total{outcome!="completed"}[30s])) / scalar(sum(rate(hw11_requests_total[30s])))','percentunit')]
for i,(title,expr,unit) in enumerate(queries):panels.append({'id':i+1,'title':title,'type':'timeseries','gridPos':{'x':i%2*12,'y':i//2*8,'w':12,'h':8},'datasource':{'type':'prometheus','uid':'hw11-prom'},'targets':[{'expr':expr,'legendFormat':'{{pod}} {{outcome}} {{__name__}}'}],'fieldConfig':{'defaults':{'unit':unit}}})
dashboard={'uid':'hw11','title':'HW11 — simulated CPU backend','schemaVersion':39,'version':1,'refresh':'5s','time':{'from':'now-15m','to':'now'},'panels':panels,'tags':['hw11','simulated']}
(root/'monitoring/dashboard.json').write_text(json.dumps(dashboard,indent=2))
add({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'hw11-grafana'},'data':{'datasources.yaml':yaml.safe_dump({'apiVersion':1,'datasources':[{'name':'Prometheus','type':'prometheus','uid':'hw11-prom','access':'proxy','url':'http://hw11-prometheus:9090','isDefault':True}]}),'dashboards.yaml':yaml.safe_dump({'apiVersion':1,'providers':[{'name':'hw11','type':'file','options':{'path':'/var/lib/grafana/dashboards'}}]}),'dashboard.json':json.dumps(dashboard)}})
def deploy(name,image,port,args=None,command=None,mounts=None,volumes=None,env=None,nodeport=None,memory='256Mi',cpu='500m'):
 container={'name':name,'image':image,'ports':[{'containerPort':port}],'resources':{'requests':{'cpu':'50m','memory':'64Mi'},'limits':{'cpu':cpu,'memory':memory}}}
 for k,v in [('args',args),('command',command),('volumeMounts',mounts),('env',env)]:
  if v:container[k]=v
 add({'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':name},'spec':{'replicas':1,'selector':{'matchLabels':{'app':name}},'template':{'metadata':{'labels':{'app':name}},'spec':{'serviceAccountName':'hw11-monitor','containers':[container],'volumes':volumes or []}}}})
 service={'selector':{'app':name},'ports':[{'port':port,'targetPort':port}]}
 if nodeport:service.update(type='NodePort');service['ports'][0]['nodePort']=nodeport
 add({'apiVersion':'v1','kind':'Service','metadata':{'name':name},'spec':service})
deploy('hw11-prometheus','prom/prometheus:v3.7.3',9090,args=['--config.file=/etc/prometheus/prometheus.yaml','--storage.tsdb.path=/prometheus','--storage.tsdb.retention.time=2h','--storage.tsdb.retention.size=256MB'],mounts=[{'name':'config','mountPath':'/etc/prometheus'},{'name':'data','mountPath':'/prometheus'}],volumes=[{'name':'config','configMap':{'name':'hw11-prometheus'}},{'name':'data','emptyDir':{'medium':'Memory','sizeLimit':'384Mi'}}],nodeport=31300,memory='512Mi')
deploy('hw11-grafana','grafana/grafana:12.2.1',3000,mounts=[{'name':'config','mountPath':'/etc/grafana/provisioning/datasources/datasources.yaml','subPath':'datasources.yaml'},{'name':'config','mountPath':'/etc/grafana/provisioning/dashboards/dashboards.yaml','subPath':'dashboards.yaml'},{'name':'config','mountPath':'/var/lib/grafana/dashboards/dashboard.json','subPath':'dashboard.json'},{'name':'data','mountPath':'/var/lib/grafana'}],volumes=[{'name':'config','configMap':{'name':'hw11-grafana'}},{'name':'data','emptyDir':{'medium':'Memory','sizeLimit':'128Mi'}}],env=[{'name':'GF_AUTH_ANONYMOUS_ENABLED','value':'true'},{'name':'GF_AUTH_ANONYMOUS_ORG_ROLE','value':'Viewer'},{'name':'GF_ANALYTICS_REPORTING_ENABLED','value':'false'},{'name':'GF_ANALYTICS_CHECK_FOR_UPDATES','value':'false'}],nodeport=31301,memory='384Mi')
deploy('hw11-state','registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.17.0',8080,args=['--namespaces=hw11','--resources=pods,deployments,horizontalpodautoscalers,replicasets'],memory='128Mi')
(root/'monitoring/stack.yaml').write_text(yaml.safe_dump_all(objects,sort_keys=False))
# Once measured, preserve exact registry manifests on regeneration.
pins=root/'monitoring/image-versions.json'
if pins.exists():
 refs={k.removeprefix('docker.io/'):v for k,v in json.loads(pins.read_text()).items()}
 for o in objects:
  if o['kind']=='Deployment':
   for c in o['spec']['template']['spec']['containers']:
    c['image']=refs.get(c['image'].removeprefix('docker.io/'),c['image'])
 (root/'monitoring/stack.yaml').write_text(yaml.safe_dump_all(objects,sort_keys=False))
