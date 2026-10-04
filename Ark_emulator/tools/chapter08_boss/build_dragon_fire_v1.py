"""Source-bound reusable Talula burn Buff pair, not complete Boss admission."""
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ark_sim import Compiler
from tools.chapter08_boss.build_talula_threshold_v3 import sha
from tools.chapter08_boss.dragon_fire_policies_v1 import providers

PROFILE = ROOT/'packages/campaign/chapter08_consumers/boss/talula.skills.source.v1.json'
SUPPLEMENT = ROOT/'packages/campaign/chapter08_consumers/special/dragon_fire.supplement.v1.json'
OUT = ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v1.json'
TIMER = 'buff/ch8/source/dragon_fire'
CHILD = 'buff/ch8/source/dragon_fire[damage]'
APPLICATION = 'rule/ch8/dragon_fire/application'


def application():
    return {'op':'buff_application','application_rule':APPLICATION,'allowed':[TIMER,CHILD]}


def build():
    assert sha(PROFILE)=='1ac74d7678be059427ae9eccd29862af2eb7a6a1f5322136da393f7c48e00113'
    assert sha(SUPPLEMENT)=='d6dd994591ac7b216c854603bf59f82291e389d49f6d9b69290be204484d5f72'
    profile, supplement = [json.loads(p.read_bytes()) for p in (PROFILE,SUPPLEMENT)]
    row = supplement['rows']['dragon_fire[damage]']['decoded']
    assert row['lifeTimeType']['value']==2 and row['triggerInterval']['value']==1
    assert row['maxStackCnt']['value']==1 and row['waitFirstTriggerInterval']['value'] is True
    node = supplement['templates']['dragon_fire[damage]']['parsed']['eventToActions']['ON_BUFF_TRIGGER'][0]
    assert node['_damageType']=='PURE' and node['_attackType']=='BUFF' and node['_ignoreForSp'] is True
    assert node['_isIncreasingToCap'] is True and node['_skipModifierEvent'] is False
    base = profile['selected_effective_skills']['DragonFire']['selected_skill']
    bb = {r['key']:r['value'] for r in base['blackboard']}
    assert bb == {'dragon_fire.duration':30.5,'dragon_fire.baseDamage':50,'dragon_fire.addOnDamage':180,'dragon_fire.addOnDuration':30}
    params = {'timer':TIMER,'child':CHILD,'duration':bb['dragon_fire.duration'],'base':bb['dragon_fire.baseDamage'],
        'addition':bb['dragon_fire.addOnDamage'],'increase_duration':bb['dragon_fire.addOnDuration']}
    p = {'schemaVersion':2,'manifest':{'id':'package/ch8/dragon_fire/source_v1','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{x.relative_to(ROOT).as_posix():sha(x) for x in (PROFILE,SUPPLEMENT,Path(__file__),Path(__file__).with_name('dragon_fire_policies_v1.py'))},
        'source_DB_skill':base,'source_recursive_Buff':supplement,
        'reference_policy':{'ramp':'Source capped increase interpreted as50+180*clamp(elapsed/30,0,1). First1s packet56, cap230 at30s; missing method body/firstpacket phase remains explicit replaceable provider.',
            'lifetime':'Parent30.5s selected from original DB skill; derived damage child permanent, max1, not removed on parent finish; damage stops without live parent. Reapplication after timer end reuses child ramp. Reset when child itself first created.',
            'packet':'Actor-sourced true BUFF, ignoreSPTrue; ordinary source/target damage hooks retained and no DEF/RES/ATK numeric read. Target death removes, source retirement retains stored source.',
            'versions':'Native DBrawBB/older FB/BSON have distinct fixed identities; case-sensitive source key stripped explicit dragon_fire prefix, no flame BB borrowed.',
            'pending':'Status resistance duration, child state reset/reignite interpretation and source retirement permission require complete source/reference tests; no complete Boss admission.'},
        'complete_boss':False,'whole_stage_executed':False,'client_verified':False}},
        'rules':[{'id':APPLICATION,'kind':'rule','contract':'buff.application','parameters':params,
            'implementation':{'type':'provider','provider':'reference.c8.dragon_fire.application'}},
            {'id':'rule/ch8/dragon_fire/pipeline','kind':'rule','contract':'damage.pipeline','parameters':params,
            'implementation':{'type':'provider','provider':'reference.c8.dragon_fire.pipeline'}}],
        'buffs':[{'id':TIMER,'kind':'buff','duration_seconds':30.5,'stacking':{'mode':'max','max_stacks':1},
            'metadata':{'native_key':'dragon_fire','native_DBrow':supplement['rows']['dragon_fire']}},
            {'id':CHILD,'kind':'buff','interval_seconds':1,'stacking':{'mode':'max','max_stacks':1},
                'removal':{'on_source_death':'retain','on_target_death':'remove'},
                'effects':[{'op':'damage','damage_type':'true','rules':{'damage.pipeline':'rule/ch8/dragon_fire/pipeline'},
                    'damage_flags':{'source_attack_type':'BUFF','ignore_for_sp':True}}],
                'metadata':{'native_key':'dragon_fire[damage]','native_DBrow':supplement['rows']['dragon_fire[damage]']}}]}
    f=deepcopy(p)
    f['entities']=[{'id':'unit/ch8/fire/compile','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'atk':0,'max_hp':100}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'abilities':['ability/ch8/fire/compile']}}]
    f['abilities']=[{'id':'ability/ch8/fire/compile','kind':'ability','activation':{'mode':'manual','on_start':[application()]},'timeline':[]}]
    f['scenarioDraft']={'id':'scene/ch8/fire/compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},
        'initialEntities':[{'definition':'unit/ch8/fire/compile','instanceAlias':'source','position':{'row':0,'col':0}}]}
    Compiler(providers=providers()).compile(f)
    return p


if __name__=='__main__':
    p=build()
    assert not OUT.exists()
    OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(OUT),'actual_compile':True,'complete_boss':False}))
