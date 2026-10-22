"""Protect the installed legacy dashboard; preserve its image, route and current authorization roles."""
import base64,copy,hashlib,json,os,sys
from pathlib import Path
import subprocess,time,uuid

def run(args,input=None,timeout=45):return subprocess.run(args,input=input,capture_output=True,text=True,timeout=timeout)
def command(args,input=None,timeout=45):
 p=run(args,input,timeout)
 if p.returncode:
  print(json.dumps({'legacyOperationFailure':args[0]+' '+args[1],'error':p.stderr[:1200]}),flush=True)
  raise RuntimeError('Legacy dashboard operation failed: '+args[0]+' '+args[1])
 return p.stdout
def obj(args):return json.loads(command(args))
if '--apply' not in sys.argv:
 raise SystemExit('Use --apply to protect the existing staging dashboard after reviewing its IAM roles and backup location')
ns='live';name='livestock-dashboard-ui';config='livestock-dashboard-access'
command(['kubectl','rollout','status','deployment/'+name,'-n',ns,'--timeout=60s'],timeout=75)
deployment=obj(['kubectl','get','deployment',name,'-n',ns,'-o','json'])
service=obj(['kubectl','get','service',name,'-n',ns,'-o','json'])
podspec=deployment['spec']['template']['spec']
assert len(podspec['containers'])==1
if any(v['name']==config for v in podspec.get('volumes',[])):
 assert not any(m['name']==config for c in podspec['containers'] for m in c.get('volumeMounts',[]))
 # Remove only the unmounted volume left by this task's earlier failed rollout.
 cleanup=[{'op':'test','path':'/spec/template','value':deployment['spec']['template']},{'op':'replace','path':'/spec/template/spec/volumes','value':[v for v in podspec.get('volumes',[]) if v['name']!=config]}]
 command(['kubectl','patch','deployment',name,'-n',ns,'--type=json','-p',json.dumps(cleanup)])
 command(['kubectl','rollout','status','deployment/'+name,'-n',ns,'--timeout=60s'],timeout=75)
 deployment=obj(['kubectl','get','deployment',name,'-n',ns,'-o','json'])
 podspec=deployment['spec']['template']['spec']
app=podspec['containers'][0]
assert app['image']=='docker.io/nahom25/livestock-dashboard-ui:0.2.0'
assert not deployment['metadata'].get('annotations',{}).get('meta.helm.sh/release-name')
assert len(service['spec']['ports'])==1 and service['spec']['ports'][0]['targetPort']==3000
assert service['spec']['selector']==deployment['spec']['selector']['matchLabels']
version=command(['kubectl','exec','-n',ns,'deploy/'+name,'--','node','--version']).strip()
assert int(version.lstrip('v').split('.')[0])>=18
pods=obj(['kubectl','get','pods','-n',ns,'-l',','.join(k+'='+v for k,v in service['spec']['selector'].items()),'-o','json'])['items']
image_id=next(c['imageID'] for p in pods for c in p.get('status',{}).get('containerStatuses',[]) if c['name']==app['name'] and c.get('ready'))
if image_id.startswith('docker-pullable://'):image_id=image_id[len('docker-pullable://'):]
assert '@sha256:' in image_id and 'livestock-dashboard-ui' in image_id
before={kind:obj(['kubectl','get',kind,name,'-n',ns,'-o','json']) for kind in ('deployment','service','virtualservice')}
snapshot=Path('/home/ec2-user/jenkins-agent/workspace/dashboard-admin-repair-private/legacy-guard-'+uuid.uuid4().hex[:12])
snapshot.mkdir(parents=True,exist_ok=True,mode=0o700)
os.chmod(snapshot,0o700)
for kind,data in before.items():
 p=snapshot/(kind+'-before.json');p.write_text(json.dumps(data));os.chmod(p,0o600)
program=base64.b64decode(base64.b64encode((Path(__file__).resolve().parent/'access-proxy.mjs').read_bytes()).decode()).decode()
roles=['Data Editor','Data Validator','Data Supervisor','Operations Administrator','Technical Administrator']
configmap={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':config,'namespace':ns},'data':{'access-proxy.mjs':program}}
env={'LEGACY_IAM_URL':'https://staff-iam.oanstaging.com','LEGACY_PUBLIC_URL':'https://livestock-dashboard.oanstaging.com','LEGACY_KEYCLOAK_ORIGIN':'https://keycloak.oanstaging.com','LEGACY_PROVIDER_ID':'3','LEGACY_REGISTRY_CLIENT_ID':'livestock-registry-staff-portal','LEGACY_VIEW_ROLES':json.dumps(roles)}
guard={'name':'registry-access','image':image_id,'imagePullPolicy':'IfNotPresent','command':['node','/etc/registry-dashboard-access/access-proxy.mjs'],'env':[{'name':k,'value':v} for k,v in env.items()],'ports':[{'name':'authenticated','containerPort':8080}],'readinessProbe':{'httpGet':{'path':'/api/health','port':'authenticated'},'initialDelaySeconds':5,'periodSeconds':5},'livenessProbe':{'tcpSocket':{'port':'authenticated'},'initialDelaySeconds':15,'periodSeconds':15},'volumeMounts':[{'name':config,'mountPath':'/etc/registry-dashboard-access','readOnly':True}],'resources':{'requests':{'cpu':'20m','memory':'64Mi'},'limits':{'memory':'192Mi'}},'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}}}
patch=[{'op':'test','path':'/spec/template','value':deployment['spec']['template']},{'op':'add','path':'/spec/template/spec/containers/-','value':guard}]
volumes=podspec.get('volumes',[])+[{'name':config,'configMap':{'name':config}}]
patch.append({'op':'add','path':'/spec/template/spec/volumes','value':volumes})
created=patched=False
try:
 command(['kubectl','create','-f','-'],json.dumps(configmap));created=True
 command(['kubectl','patch','deployment',name,'-n',ns,'--type=json','-p',json.dumps(patch)]);patched=True
 command(['kubectl','rollout','status','deployment/'+name,'-n',ns,'--timeout=180s'],timeout=200)
 # Move only the existing Service target to the verified same-pod access guard.
 command(['kubectl','patch','service',name,'-n',ns,'--type=json','-p',json.dumps([{'op':'test','path':'/metadata/resourceVersion','value':service['metadata']['resourceVersion']},{'op':'replace','path':'/spec/ports/0/targetPort','value':8080}])])
 after={kind:obj(['kubectl','get',kind,name,'-n',ns,'-o','json']) for kind in before}
 assert before['virtualservice']['spec']==after['virtualservice']['spec']
 assert app==after['deployment']['spec']['template']['spec']['containers'][0]
 assert service['spec']['selector']==after['service']['spec']['selector']
 assert deployment['metadata']['uid']==after['deployment']['metadata']['uid']
 print(json.dumps({'legacyDashboardProtected':True,'namespace':ns,'deployment':name,'originalImagePreserved':True,'existingRoutePreserved':True,'existingSelectorPreserved':True,'existingAdminRolesPreserved':True,'requiredPermission':'register:view via existing registry roles','guardImage':image_id,'guardSourceSha256':hashlib.sha256(program.encode()).hexdigest(),'backupDirectory':str(snapshot)}),flush=True)
except Exception:
 if patched:
  command(['kubectl','patch','deployment',name,'-n',ns,'--type=json','-p',json.dumps([{'op':'replace','path':'/spec/template','value':before['deployment']['spec']['template']}])])
  command(['kubectl','patch','service',name,'-n',ns,'--type=merge','-p',json.dumps({'spec':{'ports':before['service']['spec']['ports']}})])
 if created:run(['kubectl','delete','configmap',config,'-n',ns])
 print(json.dumps({'legacyGuardRolledBack':True}),flush=True)
 raise
