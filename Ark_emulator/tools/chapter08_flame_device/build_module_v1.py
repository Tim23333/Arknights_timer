"""Source level1 trap021 finiteHP/SP and fourretained rays with burn payload."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_buff_lifetime_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter08_flame_device.policies_v1 import providers
SOURCE=ROOT/'packages/campaign/chapter08_source_prepare/integration/predefines.native.v2.json'
BURN=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v8.dynamic.json'
OUT=ROOT/'packages/campaign/chapter08_consumers/flame/module.v1.reference.json'
UNIT='unit/ch8/flame/level1';ABILITY='ability/ch8/flame/explode'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    assert sha(SOURCE)=='f112ab9ad06f19bd050a997d5fe0d9d10b6c18afce3355143a2d28951e49e282'
    d=json.loads(SOURCE.read_bytes());instances=d['stages']['level_main_08-17']['instances'];assert len(instances)==10
    record=instances[0];a=record['raw_character']['phases'][0]['attributesKeyFrames'][0]['data'];skill=record['skill_selection']['level'];bb={r['key']:r['value'] for r in skill['blackboard']}
    assert (a['maxHp'],a['atk'],a['def'],a['magicResistance'],a['blockCnt'])==(6000,0,200,20,0)
    assert skill['spData']['spCost']==25 and skill['spData']['initSp']==0 and bb['damage']==1000
    pf=d['prefabs']['trap_021_flame'];mode=next(c['raw'] for c in pf['components'].values() if c['native_class']=='TrapMode');root=next(c['raw'] for c in pf['components'].values() if c['native_class']=='Trap');sk=d['skill_prefabs']['sktok_flame'];cross=next(c['raw'] for c in sk['components'].values() if c['native_class']=='CrossRangedAttack')
    assert cross['_waitForAttackEvent']==0 and cross['_preDelay']==0 and cross['_useEightDirections']==0 and root['_occupiedRemainingCharacterCnt']==0 and root['_withdrawable']==0
    pr=d['projectiles']['projectile_flame'];motion=next(c['raw'] for c in pr['components'].values() if c['native_class']=='FarthestPointMovement');hit=next(c['raw'] for c in pr['components'].values() if c['native_class']=='HitBehaviour');simple=next(c['raw'] for c in pr['components'].values() if c['native_class']=='SimpleProjectile')
    assert motion['_speed']==2.5 and simple['_lifeTime']==60 and simple['_maxHitNum']==1 and simple['_stopWhenSourceInvalid']==0
    cfg={'_'+k:v for k,v in hit['_targetOptions'].items()};cfg.update(_forceIgnoreCamouflage=hit['_ignoreCamouflage'],_needProfessionMask=0)
    stem='rule/ch8/flame/';p={'schemaVersion':2,'manifest':{'id':'package/ch8/flame/source_v1','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{str(x):sha(x) for x in (SOURCE,BURN,Path(__file__),Path(__file__).with_name('policies_v1.py'))},'required_runtime':'7e76e49e8b196f1c7ec6d3a08c7760cbb4ebc7eaa02ef778f6e71c820549fef8',
        'source_stats':record,'source_prefab':pf,'source_skill':sk,'source_projectile':pr,'source_templates':d['bson_templates'],
        'reference_policy':'Originallevel1HP6000/ATK0/DEF200/RES20/SP0→25/time1. Four cardinal fixedlaunch speed2.5 rays radius.25/nativeunmanagedlife60 maxhit1. Neutral source2 explicitlyenemy-targetmask byabsolute player-sidebit, firstqualified collision. FixedValueDamage1000MAGICAL reads currentRES/hook, thenburn application. Device retires withdrawn afterlaunch, retainedrays remain; noHP0(fakeatk) needed. Predelay0 waitsAttackEventFalse exact; Die visualanimation notdelay semantic. Mixed20250327deviceprefabversion retained, body/casefold/projectilegeometry reference declared.',
        'whole_stage_executed':False,'client_verified':False}},'entities':[],'abilities':[],'projectiles':[],'rules':[],'buffs':[]}
    fire=json.loads(BURN.read_bytes());p['rules']+=fire['rules'];p['buffs']+=fire['buffs']
    p['rules'] += [{'id':stem+'motion','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'reference.c8.flame.ray'}},
        {'id':stem+'eligibility','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}},
        {'id':stem+'collision','kind':'rule','contract':'projectile.collision','dependencies':[stem+'eligibility'],'implementation':{'type':'provider','provider':'model.projectile.qualified_swept_ray'}},
        {'id':stem+'damage','kind':'rule','contract':'damage.pipeline','parameters':{'damage':1000,'minimum_ratio':.05},'metadata':{'input_bindings':{'resistance':{'entity':'target','attribute':'mres'}}},'implementation':{'type':'provider','provider':'reference.c8.flame.fixed_arts'}}]
    effects=[]
    eligibility={'rule':stem+'eligibility','parameters':{'source_configuration':{**cfg,'_targetSide':1},'side_policy':'relative_ally_enemy','neutral_policy':'absolute_mask','defaults':deepcopy(DEFAULT_STATE)}}
    for direction in ('up','right','down','left'):
        pid='projectile/ch8/flame/'+direction;p['projectiles'].append({'id':pid,'kind':'projectile','motion':{'rule':stem+'motion','parameters':{'direction':direction,'speed':2.5,'extent_policy':'map_bounds'}},'collision':{'rule':stem+'collision','allow_other_targets':True,'parameters':{'qualified_ray':True,'radius':.25,'exclude_source':True,'eligibility':eligibility}},'lifetime_seconds':60,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,'completion_blocking':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':True,'hit_on_reach':False,'force_reach_on_expire':False,'hit_on_expire':False}})
        effects.append({'at':0,'effect':{'op':'damage','target':'source','damage_type':'arts','scale':0,'projectile_definition':pid,'rules':{'damage.pipeline':stem+'damage'},'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False},'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'},'on_success':[{'op':'buff_application','application_rule':'rule/ch8/dragon_fire/application','allowed':['buff/ch8/source/dragon_fire','buff/ch8/source/dragon_fire[damage]']}]}})
    effects.append({'at':0,'effect':{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}})
    p['abilities']=[{'id':ABILITY,'kind':'ability','activation':{'mode':'manual','parameters':{'auto_only':True,'auto_when_ready':True,'requires_targets':False},'costs':[{'resource':'sp','amount':25}]},'timeline':effects}]
    modebuff='buff/ch8/flame/tile';immunes='buff/ch8/flame/immunes';p['buffs']+=[{'id':modebuff,'kind':'buff','effects':[{'op':'apply_terrain_overlay','target':'source','parameters':{'key':'native_flame_mode','priority':0,'values':{'buildableType':0,'passableMask':2,'physicalHeight':mode['_rewriteHeight']},'preserve':['heightType','advancedBuildMask']}}],'on_remove':[{'op':'remove_terrain_overlay','target':'source','parameters':{'key':'native_flame_mode'}}]},
        {'id':immunes,'kind':'buff','selection_flags':{'abnormal_immunes':[0,16,12],'abnormal_combo_immunes':[0]}}]
    p['entities']=[{'id':UNIT,'kind':'entity','tags':['native_device','flame'],'components':{'attributes':{'base':{'max_hp':6000,'atk':0,'def':200,'mres':20,'block_count':0,'attack_interval':1,'attack_speed_ratio':1}},'resources':{'hp':{'initial':6000,'capacity_attribute':'max_hp','role':'health'},'sp':{'initial':0,'capacity':25,'recovery_rate':1,'recovery':{'mode':'continuous'}}},'selection_state':{'side':2,'motion':1,'category':1,'unit_type':4},'spatial':{},'abilities':[ABILITY],'buffs':{'initial':[modebuff,immunes]},'lifecycle':{'policy':'policy/ark_lifecycle'},'tile_occupancy':{'blocks_deployment':True,'exclusive':True,'targetable':True,'withdrawable':False}}}]
    f=deepcopy(p);f['scenarioDraft']={'id':'scene/flame/compile','ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':5},'initialEntities':[{'definition':UNIT,'instanceAlias':'flame','position':{'row':2,'col':2}}]};Compiler(providers=providers()).compile(f);return p

if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(sha(OUT))
