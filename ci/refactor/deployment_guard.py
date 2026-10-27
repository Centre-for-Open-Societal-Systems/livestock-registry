"""Check the registered Farmer extension configuration without exposing values."""
import argparse
import base64
import json
from pathlib import PurePosixPath
import subprocess
import sys
from urllib.parse import urlsplit

PREFIX='COSS_FARMER_'
REQUIRED=('DCI_URL','SENDER_ID','SOURCE_ID','SIGNING_KID','SOURCE_KID','CONSENT_AUDIENCE',
          'CONSENT_CONTROLLER','CONSENT_PURPOSE','CONSENT_SCOPES','SOURCE_PARTNER_ID',
          'AWE_TOKEN_URL','AWE_CLIENT_ID')
FILES=('SIGNING_KEY_FILE','SOURCE_PUBLIC_KEY_FILE','RECORD_CONTRACT_FILE','AWE_CLIENT_SECRET_FILE')


def resources(stream):
    text=stream.read().strip()
    result=[]
    while text:
        document,end=json.JSONDecoder().raw_decode(text)
        result.extend(document.get('items',[]) if document.get('kind')=='List' else [document])
        text=text[end:].lstrip()
    return result


def check(items,release,namespace,secret_loader=None):
    seen=[]
    for suffix in ('staff-portal-api','celery-worker','celery-beat-producer'):
        name=release+'-'+suffix
        targets=[item for item in items if item.get('kind')=='Deployment' and item.get('metadata',{}).get('name')==name]
        assert len(targets)==1, 'Required extension Deployment missing or duplicated: '+suffix
        target=targets[0]
        assert target['metadata'].get('namespace',namespace)==namespace, 'Wrong extension namespace'
        pod=target['spec']['template']['spec']
        containers=[item for item in pod['containers'] if item['name']==suffix]
        assert len(containers)==1, 'Required extension container missing or duplicated'
        container=containers[0]
        entries=container.get('env',[])
        env={item['name']:item for item in entries}
        assert len(env)==len(entries), 'Duplicate extension environment setting'
        def value(key): return str(env.get(PREFIX+key,{}).get('value','')).strip()
        for key in REQUIRED+FILES:
            assert value(key), 'Required extension setting missing: '+PREFIX+key
        for key in ('DCI_URL','AWE_TOKEN_URL'):
            uri=urlsplit(value(key))
            assert uri.scheme in ('https','http') and uri.hostname and not (uri.username or uri.password or uri.query or uri.fragment), 'Invalid extension service URL'
        for key in ('SIGNING_ALGORITHM','SOURCE_ALGORITHM'):
            assert (value(key) or 'RS256') in ('RS256','PS256','EdDSA'), 'Unsafe extension signature algorithm'
        volumes={item['name']:item for item in pod.get('volumes',[])}
        for key in FILES:
            path=PurePosixPath(value(key))
            assert path.is_absolute() and '..' not in path.parts, 'Invalid extension configuration file path'
            matches=[item for item in container.get('volumeMounts',[]) if
                     path==PurePosixPath(item['mountPath']) or PurePosixPath(item['mountPath']) in path.parents]
            assert len(matches)==1 and matches[0].get('readOnly') is True, 'Required read-only extension configuration mount missing'
            volume=volumes.get(matches[0]['name'],{})
            private=key in ('SIGNING_KEY_FILE','AWE_CLIENT_SECRET_FILE')
            source=volume.get('secret',{}) if private else volume.get('configMap',volume.get('secret',{}))
            source_name=source.get('secretName',source.get('name'))
            assert source_name and not source.get('optional',False), 'Required extension Secret/ConfigMap volume missing'
            if private and secret_loader:
                secret=secret_loader(namespace,source_name)
                assert secret.get('metadata',{}).get('namespace')==namespace, 'Wrong extension Secret namespace'
                data=secret.get('data',{})
                volume_items=source.get('items') or [{'key':name,'path':name} for name in data]
                relative=matches[0].get('subPath') or path.relative_to(PurePosixPath(matches[0]['mountPath'])).as_posix()
                keys=[item['key'] for item in volume_items if item['path']==relative]
                assert len(keys)==1 and base64.b64decode(data.get(keys[0],''),validate=True).strip(), 'Required extension Secret key empty or missing'
        seen.append(name)
    return {'farmerReferenceExtensionGuard':'PASS','deployments':seen,'liveSecretsChecked':secret_loader is not None}


def live_secret(namespace,name):
    result=subprocess.run(['kubectl','get','secret',name,'-n',namespace,'-o','json'],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,'Required extension Secret unavailable'
    return json.loads(result.stdout)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',required=True)
    parser.add_argument('--namespace',required=True)
    parser.add_argument('--check-live-secret',action='store_true')
    args=parser.parse_args()
    try:
        print(json.dumps(check(resources(sys.stdin),args.release,args.namespace,live_secret if args.check_live_secret else None)))
    except (AssertionError,ValueError,KeyError,TypeError,OSError,subprocess.TimeoutExpired) as error:
        reason=str(error) if isinstance(error,AssertionError) else 'Invalid extension configuration or unavailable resource'
        raise SystemExit('Farmer reference guard failed: '+reason) from None


if __name__=='__main__': main()
