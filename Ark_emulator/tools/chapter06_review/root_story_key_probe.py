"""Separate actual C6 predefinition identity and ambiguity checks."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter06_review.story_keys_v5 import convert,digest


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    planpath=ROOT/'packages/campaign/chapter06_plans/source.plan.json'
    plan=json.loads(planpath.read_bytes());native=plan['stages']['level_main_06-15']['native_document']
    profile=json.loads((ROOT/'validation/campaign/chapter06_review/converter_v5_v1/actual_source_mapping_profile.json').read_bytes())
    definitions={e['activation_key']:e['definition'] for e in profile['bindings']}
    converted=convert(native,'level_main_06-15',definitions,story_key_profile=profile)
    assert converted['native_predefines']==native['predefines']
    initial=converted['initial_entities']
    assert len(initial)==3 and native['options']['characterLimit']==0
    rows=len(native['mapData']['map'])
    for raw,item in zip(native['predefines']['characterInsts'],initial):
        assert item['parameters']['native_instance']==raw
        assert raw['alias'] is None and raw['hidden'] is True
        assert item['active'] is False and item['registration_key']==raw['inst']['characterKey']
        assert item['position']=={'row':rows-1-raw['position']['row'],'col':raw['position']['col']}
        assert item.get('instanceAlias') is None and raw['skillIndex']==-1
    cases=[]
    for name,mutate in [('duplicate_same_key',lambda n:n['predefines']['characterInsts'].append(deepcopy(n['predefines']['characterInsts'][0]))),
                         ('wrong_hidden_integer',lambda n:n['predefines']['characterInsts'][0].update(hidden=1)),
                         ('colliding_alias',lambda n:n['predefines']['characterInsts'][1].update(alias=n['predefines']['characterInsts'][0]['inst']['characterKey'])),
                         ('unknown_native_activation',lambda n:next(a for w in n['waves'] for f in w['fragments'] for a in f['actions'] if a['actionType']=='ACTIVATE_PREDEFINED').update(key='$avatar_amiya'))]:
        copy=deepcopy(native);mutate(copy);p=deepcopy(profile);p['native_document_digest']=digest(copy)
        try:convert(copy,'level_main_06-15',definitions,story_key_profile=p)
        except (ValueError,KeyError):cases.append({'case':name,'rejected':True})
        else:raise AssertionError(name)
    try:convert(native,'level_main_06-15',definitions)
    except ValueError:cases.append({'case':'no_explicit_profile','rejected':True})
    else:raise AssertionError('default profile bypass')
    out=ROOT/'validation/campaign/chapter06_review/root_story_key_probe';assert not out.exists();out.mkdir(parents=True)
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'source_sha':sha(planpath),'converted':initial,'negative_cases':cases,
        'helper_sha':sha(ROOT/'tools/chapter06_review/story_keys_v5.py'),'scope':'Independent actual source registration keys and all original fields; proposed NPC definition IDs, no source flag consumer or whole-stage approval'},indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'passed':True,'cases':len(cases),'sha':sha(target)}))


if __name__=='__main__':main()
