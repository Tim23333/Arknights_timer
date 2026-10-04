"""Public burn preparation for real 35s explosion, preserving source cooldown."""
import json
from pathlib import Path
from tools.chapter08_bsnake_skills import author_v2 as old
from tools.chapter08_bsnake_skills.build_v1 import BASE,TIMER,CHILD,application,sha
from ark_sim.adapters.api import implementation_digest
ROOT=old.ROOT;OUT=BASE/'skills_author_v3';original=old.package
def package(mode=0,kind='ignite'):
    p=original(mode,kind)
    if kind=='explode':
        p['entities'][1]['components'].pop('buffs',None)
        p['selectors'].append({'id':'selector/fixture/prepare','kind':'selector','region':{'type':'all'},'filters':[{'tag':'primary'}]})
        p['entities'][1]['tags'].append('primary')
        p['abilities'].append({'id':'ability/fixture/prepare','kind':'ability','activation':{'mode':'manual'},'selector':'selector/fixture/prepare','timeline':[{'at':0,'effect':application()}]})
        p['entities'][0]['components']['abilities'].append('ability/fixture/prepare')
        p['scenarioDraft']['commands']=[{'at':900,'action':'skill','source':'boss','ability':'ability/fixture/prepare'}]
        p['manifest']['metadata']['fixture']+=' Public fixture skill at900 binds source burn at actual target; original explosion35/35 unchanged.'
    return p
def main():
    assert implementation_digest()==old.CORE
    old.package=package;old.OUT=OUT;OUT.mkdir(exist_ok=True)
    rows=[old.run(m,k) for m in (0,1) for k in ('ignite','explode')]
    for row in rows:
        obs=row['observations'];hits=[(e['time'],e['payload']['target'],e['payload']['amount']) for e in obs if e['type']=='damage.accepted']
        if row['kind']=='ignite':
            assert hits==[(635,3,56),(635,4,56),(665,3,62),(665,4,62)],hits
        else:
            normal=[(e['time'],e['payload']['target'],e['payload']['amount']) for e in obs if e['type']=='damage.accepted' and e['payload']['damage_flags']['source_attack_type']=='NORMAL']
            assert normal==[(1082,3,616),(1082,4,462),(1082,5,308)],normal
            areas=[e for e in obs if e['type']=='area.resolved'];assert len(areas)==1 and areas[0]['payload']['members']==[4,5]
            assert [(e['time'],e['payload']['target']) for e in obs if e['type']=='buff.removed' and e['payload']['buff']==TIMER]==[(1082,3)]
            assert [(t,target,amount) for t,target,amount in hits if t==1113]==[(1113,4,56),(1113,5,56)]
    out=OUT/'report.json';assert not out.exists();out.write_text(json.dumps({'status':'four_source_clock_and_payload_cases_passed','core':old.CORE,'module_sha256':sha(BASE/'skills.module.v3.json'),'rows':rows,'ordinary_phase_and_stage_scope':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(sha(out))
if __name__=='__main__':main()
