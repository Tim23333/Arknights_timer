"""Correct source reset policy through existing pure ability.recovery contract."""
import json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_selection_context_clock_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from tools.chapter08_boss.build_talula_threshold_v3 import sha
from tools.chapter08_boss.talula_skill_policies_v2 import providers
PARENT=ROOT/'packages/campaign/chapter08_consumers/boss/talula.skills.v1.reference.json'
OUT=ROOT/'packages/campaign/chapter08_consumers/boss/talula.skills.v2.reference.json'

def build():
    assert sha(PARENT)=='5a912b165a7d87fd9ba5547a62ddd9aa883775288edb3d5a09c7fe7c71a29d2c'
    p=json.loads(PARENT.read_bytes());meta=p['manifest']['metadata'];meta['source_locks'].update({x.relative_to(ROOT).as_posix():sha(x) for x in (PARENT,Path(__file__),Path(__file__).with_name('talula_skill_policies_v2.py'))})
    p['manifest']['id']='package/ch8/talula/skills_v2';meta['source_cooldown_policy']='Source EnemySkill resetMainAbilityCdWhenCastEnd0 selected as start-relative reference. Existing V2 finish-relative recovery is compensated using actual quantized source animation duration/OnAttack. Same cooldown_seconds literal unchanged; if duration exceedsCD next available afterfinish. V1failed original992vs900 preserved.'
    for a in p['abilities']:
        if a['activation']['mode']!='manual':continue
        row=a['metadata']['source_skill'];an=row['animation_binding'];event=next(e for e in an['events'] if e['name']=='OnAttack');rid=a['id'].replace('ability/','rule/')+'/start_recovery'
        a['rules']['ability.recovery']=rid;p['rules'].append({'id':rid,'kind':'rule','contract':'ability.recovery','parameters':{'mapping_speed':an['mapping']['speed'],'source_duration':an['duration']['seconds'],'source_delay':event['seconds']},'implementation':{'type':'provider','provider':'reference.c8.talula.start_cooldown'}})
    f=deepcopy(p);f['scenarioDraft']={'id':'scene/talula/skills_v2_compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':0,'col':0}}]};Compiler(providers=providers()).compile(f);return p

if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(OUT),'actual_compile':True}))
