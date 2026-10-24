"""Reject new-dev public routing drift in kubectl's rendered-manifest JSON.

Usage: kubectl create --dry-run=client --validate=false -f rendered.yaml -o json |
       python3 ci/check-new-dev-routes.py crop --release cropsown-registry --namespace crop
No apply, credentials, dependencies, or manifest values are logged here.
"""
import argparse
import base64
import json
import re
import sys

DOMAIN='development.oanstaging.com'
GATEWAY='istio-system/development'
LEGACY=re.compile(r'(?:[a-z0-9-]+-development|[a-z0-9-]+\.commons-dev)\.oanstaging\.com')


def load_resources(stream):
    # kubectl can print one JSON object per YAML document, rather than a List.
    decoder=json.JSONDecoder();text=stream.read().strip();items=[]
    while text:
        document,end=decoder.raw_decode(text)
        items.extend(document.get('items',[]) if document.get('kind')=='List' else [document])
        text=text[end:].lstrip()
    return {'kind':'List','items':items}


def check(document,registry,release,namespace):
    resources=document.get('items',[]) if document.get('kind')=='List' else [document]
    assert resources,'No rendered resources'
    expected={release+'-staff-portal-ui':registry+'-registry.'+DOMAIN,
        release+'-staff-portal-api':'staff-'+registry+'.'+DOMAIN,
        release+'-partner-api':'partner-'+registry+'.'+DOMAIN}
    if registry=='livestock':expected[release+'-id-generator']='idgenerator-livestock.'+DOMAIN
    found={}
    def inspect(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if 'COOKIE' in key.upper() and 'DOMAIN' in key.upper():
                    assert item!='.oanstaging.com','Legacy cookie scope'
                inspect(item)
            if str(value.get('name','')).upper().endswith('COOKIE_DOMAIN'):
                assert value.get('value')!='.oanstaging.com','Legacy cookie scope'
            if value.get('kind')=='Secret':
                for encoded in (value.get('data') or {}).values():
                    try:decoded=base64.b64decode(encoded,validate=True).decode('utf-8')
                    except (ValueError,UnicodeDecodeError):continue
                    inspect(decoded)
        elif isinstance(value,list):
            for item in value:inspect(item)
        elif isinstance(value,str):assert not LEGACY.search(value),'Legacy public URL in rendered configuration'
    for resource in resources:
        inspect(resource)
        metadata=resource.get('metadata',{})
        assert metadata.get('namespace',namespace)==namespace,'Resource outside target namespace'
        if resource.get('kind')!='VirtualService':continue
        name=metadata['name'];spec=resource['spec'];hosts=spec.get('hosts',[])
        gateways=spec.get('gateways',[])
        public=[h for h in hosts if h.endswith('.'+DOMAIN)]
        if public:
            assert len(public)==len(hosts),'Mixed private/public route'
            assert gateways==[GATEWAY],'Public route does not use shared development Gateway'
        elif GATEWAY in gateways:
            raise AssertionError('Private route exposed through shared development Gateway')
        if name in expected:
            assert hosts==[expected[name]],'Required registry route has incorrect host'
            assert gateways==[GATEWAY],'Required registry route has incorrect Gateway'
            assert name not in found,'Duplicate registry route'
            found[name]=hosts[0]
    assert set(found)==set(expected),'Required public registry routes missing'
    return {'registry':registry,'namespace':namespace,'publicRegistryRoutes':len(found),'routingGuard':'passed'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registry',choices=['crop','livestock'])
    parser.add_argument('--release',required=True)
    parser.add_argument('--namespace',required=True)
    args=parser.parse_args()
    try:
        report=check(load_resources(sys.stdin),args.registry,args.release,args.namespace)
    except (AssertionError,ValueError,KeyError,TypeError) as error:
        # Report a fixed reason, never JSON/Secret contents from parser errors.
        reason=str(error) if isinstance(error,AssertionError) else 'Invalid rendered manifest JSON'
        print('New-dev routing guard failed: '+reason,file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(report))


if __name__=='__main__':main()
