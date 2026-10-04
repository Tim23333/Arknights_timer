"""Adversarial middle-value mutations preserve final runtime output, then fail audit."""
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.chapter06_story_ledger_v1 import audit


def main():
    source=ROOT/'validation/campaign/chapter06_story_join_v3/06-15.life99999.json'
    journal=Path('E:/ArkSimEvidence/campaign/06_17_d509_story_v3/full_v1.events.jsonl')
    data=json.loads(source.read_bytes());events=[json.loads(line) for line in journal.read_text(encoding='utf8').splitlines()]
    original=audit(events,data);assert original['passed'];cases=[]
    changes=[('hp_delta',lambda es:next(e for e in es if e['type']=='resource.changed' and e['payload'].get('resource')=='hp' and e['payload'].get('delta',0)<0)['payload'].__setitem__('delta',-1999)),
        ('damage_amount',lambda es:next(e for e in es if e['type']=='damage.accepted')['payload'].__setitem__('amount',1999)),
        ('blood_raw_amount',lambda es:next(e for e in es if e['type']=='damage.accepted' and e['payload'].get('source_policy')=='none')['payload'].__setitem__('pipeline_amount',1999)),
        ('prebirth_hp',lambda es:next(e for e in es if e['type']=='resource.changed' and e['payload'].get('resource')=='hp' and e['payload'].get('delta')==0)['payload'].__setitem__('value',95001))]
    for name,change in changes:
        es=deepcopy(events);change(es);result=audit(es,data);assert not result['passed'],name
        cases.append({'case':name,'rejected':True,'failures':result['failures'][:2]})
    es=deepcopy(events);i=next(i for i,e in enumerate(es) if e['type']=='area.resolved');es.insert(i+1,deepcopy(es[i]))
    for i,e in enumerate(es,1):e['id']=i
    result=audit(es,data);assert not result['passed'];cases.append({'case':'duplicate_source_area_same_cast','rejected':True,'failures':result['failures'][:2]})
    p=deepcopy(data);enemy=next(d for d in p['definitions'] if d['kind']=='entity' and 'enemy' in d.get('tags',[]));enemy['components']['resources']['hp']['initial']+=1
    result=audit(events,p);assert not result['passed'];cases.append({'case':'source_initial_hp_mismatch','rejected':True,'failures':result['failures'][:2]})
    out=ROOT/'validation/campaign/chapter06_story_ledger_v1/negative_verification.json';assert not out.exists()
    proof={'passed':True,'original_counts':original['counts'],'cases':cases,'original_package_sha':hashlib.sha256(source.read_bytes()).hexdigest(),
        'journal_sha':hashlib.sha256(journal.read_bytes()).hexdigest(),'helper_sha':hashlib.sha256((ROOT/'tools/trace_audit/chapter06_story_ledger_v1.py').read_bytes()).hexdigest(),
        'scope':'Source constrained story HP/blood/area ledger middle-value mutations, actual final run remains unchanged. No arbitrary numeric-allfields/client approval.'}
    out.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'negative_cases':len(cases),'sha':hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
