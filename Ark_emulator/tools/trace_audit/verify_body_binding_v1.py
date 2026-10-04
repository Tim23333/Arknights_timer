"""Independent source actor and base-field mutations must fail with same damage."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.body_binding_v1 import audit


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    base=ROOT/'validation/trace_audit/source_golden_v3';package=json.loads((base/'input.json').read_bytes())
    rows=[];sample=None
    with (base/'events.jsonl').open(encoding='utf8') as f:
        for line in f:
            e=json.loads(line);rows.append(e)
            if e['type']=='calculation' and e['payload']['calculation_id']=='damage.pipeline':sample=e;break
    assert sample
    out=ROOT/'validation/trace_audit/root_body_binding_v1';results=[]
    for name,mutate in [('source_body_id',lambda e:e['payload']['trace']['inputs']['source'].update(id=9999)),
                        ('target_body_definition',lambda e:e['payload']['trace']['inputs']['target'].update(definition_id='unit/missing')),
                        ('source_base_attack',lambda e:e['payload']['trace']['inputs']['source']['components']['attributes']['base'].update(atk=601))]:
        path=out/(name+'.jsonl');assert not path.exists()
        with path.open('x',encoding='utf8',newline='') as f:
            for row in rows:
                e=deepcopy(row)
                if e['id']==sample['id']:
                    value=deepcopy(e['payload']['value']);mutate(e);assert e['payload']['value']==value
                f.write(json.dumps(e)+'\n')
        r=audit(path,package);assert not r['passed'] and r['failures'];results.append({'case':name,'rejected':True,'first_difference':r['failures'][0],'input_sha':sha(path)})
    target=out/'verification.json';assert not target.exists();target.write_text(json.dumps({'passed':True,'cases':results,
        'helper_sha':sha(ROOT/'tools/trace_audit/body_binding_v1.py'),'source_journal_sha':sha(base/'events.jsonl'),
        'package_sha':sha(base/'input.json'),'scope':'Identity/base source binding only; arithmetic final value unchanged; unknown effective/dynamic values remain pending'},indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'passed':True,'cases':len(results),'sha':sha(target)}))


if __name__=='__main__':main()
