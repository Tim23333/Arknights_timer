"""Source-bound Faust attack/invincible consumer; branch skill remains separate."""
import argparse,hashlib,json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'packages/campaign/chapter05_sources/native.reference.json'
PIN='323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5'
PREFIX='ch5/faust';OUT=ROOT/'packages/campaign/chapter05_boss/faust/combat.v4.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert sha(SOURCE)==PIN;source=json.loads(SOURCE.read_bytes());v=source['variants']['enemy_1508_faust@0/86350d42c005ccb6']
    db=v['native_enemy']['resolved'];a=db['attributes'];prefab=source['prefabs'][v['prefab_key']]
    root=next(c['raw'] for c in prefab['components'].values() if c['native_class']=='Enemy')
    mover=next(c['raw'] for c in prefab['components'].values() if c['native_class']=='MoveController')
    selector=next(c['raw'] for c in prefab['components'].values() if c['native_class']=='AdvancedSelector' and c['gameobject_name']=='Trigger')
    assert (a['maxHp'],a['atk'],a['def'],a['baseAttackTime'],db['rangeRadius'])==(37000,1000,350,5,20)
    assert db['talentBlackboard'][0]['value']==150 and selector['_targetMotion']==1
    defaults={'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],
        'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],'target_free':False,
        'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False}
    rules=[{'id':'rule/'+PREFIX+'/eligible','kind':'rule','contract':'targeting.eligibility',
        'implementation':{'type':'provider','provider':'model.targeting.eligibility'}},
        {'id':'rule/'+PREFIX+'/score','kind':'rule','contract':'targeting.score','implementation':{'type':'expression',
            'expression':"-100000*(inputs.candidate.components.attributes.base.taunt_level if 'taunt_level' in inputs.candidate.components.attributes.base else 0)-inputs.candidate.id"}},
        {'id':'rule/'+PREFIX+'/steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}},
        {'id':'rule/'+PREFIX+'/trajectory','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}},
        {'id':'rule/'+PREFIX+'/collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}},
        {'id':'rule/'+PREFIX+'/invincible','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph',
            'nodes':[{'id':'answer','expression':"{'accepted':False,'amount':0,'allocations':[],'events':[]}"}],'output':'nodes.answer'}},
        {'id':'rule/'+PREFIX+'/active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'True'}},
        {'id':'rule/'+PREFIX+'/block_policy','kind':'rule','contract':'blocking.eligibility',
            'implementation':{'type':'provider','provider':'model.blocking.status'},
            'parameters':{'block_free_flag':3,'base_rule':'rule/ark_block_eligibility'},
            'dependencies':['rule/ark_block_eligibility']}]
    projectiles=[];abilities=[]
    for name,animation,key,scale in [('normal','Attack','projectile_faust',1),('critical','Skill_1','projectile_faust_s1',2)]:
        raw=next(c['raw'] for c in prefab['components'].values() if c['native_class']=='RangedAttack' and c['raw']['_animKey']==animation)
        anim=source['animations'][v['prefab_key']]['parsed']['animations'][animation]
        assert anim['events'][0]['frame']==40 and anim['duration']['frame']==90
        mov=next(c['raw'] for c in source['projectiles'][key]['components'].values() if c['native_class']=='AdvancedMovement')
        proj=next(c['raw'] for c in source['projectiles'][key]['components'].values() if c['native_class']=='SimpleProjectile')
        assert mov['_speed']==10 and proj['_lifeTime']==5 and proj['_stopWhenSourceInvalid']==0
        projectiles.append({'id':'projectile/'+PREFIX+'/'+name,'kind':'projectile',
            'motion':{'rule':'rule/'+PREFIX+'/trajectory','parameters':{'mode':'homing','speed':10}},
            'collision':{'rule':'rule/'+PREFIX+'/collision','parameters':{'enabled':True,'radius':0}},
            'lifetime_seconds':5,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,
            'attach_at_launch':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'cancel',
                'target_hidden':'cancel','finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True},'on_invalid':[]})
        ability={'id':'ability/'+PREFIX+'/'+name,'kind':'ability','selector':'selector/'+PREFIX+'/target',
            'rules':{'targeting.score':'rule/'+PREFIX+'/score'},'duration_seconds':3,
            'activation':{'mode':'automatic_attack' if name=='normal' else 'manual','parameters':{'auto_only':True}},
            'timeline':[{'at':40,'effect':{'op':'damage','damage_type':'physical','scale':scale,
                'projectile_definition':'projectile/'+PREFIX+'/'+name,'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False},
                'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}}],
            'metadata':{'source_combat':raw,'source_animation':anim}}
        if name=='critical':
            ability.update(initial_cooldown_seconds=17,cooldown_seconds=17)
            ability['activation']['parameters']['requires_targets']=True
        abilities.append(ability)
    ids=[x['id'] for x in abilities]
    entity={'id':'unit/'+PREFIX+'/level0','kind':'entity','tags':['enemy','boss','faust'],
        'metadata':{'native_variant_id':v['variant_id'],'native_reference':v['native_reference']},'components':{
            'attributes':{'base':{'max_hp':37000,'atk':1000,'def':350,'mres':35,'move_speed':.5,'attack_interval':5,
                'attack_speed_ratio':1,'mass_level':5,'block_cost':root['_blockVolume']}},
            'resources':{'hp':{'initial':37000,'capacity_attribute':'max_hp','role':'health'}},
            'spatial':{'motion_mode':0,'steering':{'rule':'rule/'+PREFIX+'/steering','parameters':{
                'response_factor':mover['_steeringFactor'],'max_acceleration':mover['_maxSteeringForce'],'arrival_radius':.05}}},
            'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2,'abnormal_immunes':[0,12,18],
                'abnormal_flags':[3],'abnormal_combo_immunes':[0]},
            'buffs':{'initial':['buff/'+PREFIX+'/invincible']},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':2},
            'abilities':ids,'ability_arbitration':{'priority_order':'higher_first','busy':'all_casts',
                'entries':[{'ability':aid,'priority':priority,'attack_clock':True,'require_attack_control':True,
                    'condition':'True','parameters':{}} for aid,priority in [(ids[1],0),(ids[0],-1)]]},
            'behavior':{'machine':'behavior/'+PREFIX+'/combat'}}}
    return {'schemaVersion':2,'manifest':{'id':'package/ch5/faust/combat_partial','requires':['preset/ark_standard'],
        'metadata':{'source_locks':{str(SOURCE.relative_to(ROOT)):PIN},'builder_sha':sha(Path(__file__)),
            'status':'combat_consumer_pending_peer_and_SummonBallis','full_stage_executed':False,'client_verified':False,
            'stage_rules':{'blocking.eligibility':'rule/'+PREFIX+'/block_policy'},
            'policies':{'range':'DB20 scaled circle','target_order':'highest raw taunt then latest entity id; replaceable',
                'invincible':'150s actor damage afterhook cancels packet; active_rule enables exact expiry settle',
                'critical_clock':'shared normal5s, cooldown17 from cast finish; explicit reference; source body unverified',
                'projectile':'planar homing10/s trace point, source_retire retain, lifetime5 force hit; native camera/collider unverified'},
            'pending':['SummonBallis15/30 priority1 Skill2frame27/50 andbranch7/10','Actual ballista consumers/full5-10']}},
        'entities':[entity],'abilities':abilities,'projectiles':projectiles,'rules':rules,
        'selectors':[{'id':'selector/'+PREFIX+'/target','kind':'selector','region':{'type':'radius','radius':20},
            'filters':[{'tag':'player'},{'state':'alive'}],'limit':1,'eligibility':{'rule':'rule/'+PREFIX+'/eligible',
                'parameters':{'source_configuration':selector,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}}}],
        'buffs':[{'id':'buff/'+PREFIX+'/invincible','kind':'buff','duration_seconds':150,
            'active_rule':'rule/'+PREFIX+'/active','selection_flags':{'abnormal_flags':[5]},
            'damage_hooks':[{'phase':'after','rule':'rule/'+PREFIX+'/invincible'}]}],
        'behaviors':[{'id':'behavior/'+PREFIX+'/combat','kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],
            'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,
                'selectors':[{'key':'normal','selector':'selector/'+PREFIX+'/target'}],
                'cast_groups':[{'key':'combat','abilities':ids}],
                'parameters':{'target_key':'normal','blocked_target':False,'stop_on_target':True,'stop_cast_groups':['combat']}}]}}]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:assert OUT.read_bytes()==raw
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        with OUT.open('xb') as f:f.write(raw)
    print(json.dumps({'sha':hashlib.sha256(raw).hexdigest(),'full_stage_executed':False}))
if __name__=='__main__':main()
