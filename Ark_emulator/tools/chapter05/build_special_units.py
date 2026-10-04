"""Exact hammer attack-SP/stun and lunmag source ranged-combat consumers."""
import argparse,hashlib,json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'packages/campaign/chapter05_sources/native.reference.json'
PIN='323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5'
OUT=ROOT/'packages/campaign/chapter05_units/special/model.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert sha(SOURCE)==PIN;source=json.loads(SOURCE.read_bytes());prefix='ch5/special'
    rules=[{'id':'rule/'+prefix+'/windup','kind':'rule','contract':'ability.windup','parameters':{'min_speed':.01},
        'implementation':{'type':'expression','expression':'inputs.timing_parameters.seconds/max(inputs.attributes.attack_speed_ratio,params.min_speed)'}},
        {'id':'rule/'+prefix+'/stun','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'0 in inputs.status.abnormal_flags'}},
        {'id':'rule/'+prefix+'/eligibility','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}},
        {'id':'rule/'+prefix+'/combat_guard','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'graph',
            'nodes':[{'id':'base','rule':'rule/'+prefix+'/eligibility','inputs':{k:'inputs.'+k for k in ('source','candidate','selector','parameters','selection_states')}},
                {'id':'answer','expression':"{'accepted':nodes.base.accepted and (inputs.source.components.runtime.blocked_by == None or inputs.source.components.runtime.blocked_by == inputs.candidate.id),'reason':nodes.base.reason}"}],
            'output':'nodes.answer'}},
        {'id':'rule/'+prefix+'/score','kind':'rule','contract':'targeting.score','implementation':{'type':'expression',
            'expression':"-100000*(inputs.candidate.components.attributes.base.taunt_level if 'taunt_level' in inputs.candidate.components.attributes.base else 0)-inputs.candidate.id"}},
        {'id':'rule/'+prefix+'/steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}},
        {'id':'rule/'+prefix+'/trajectory','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}},
        {'id':'rule/'+prefix+'/collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}]
    p={'schemaVersion':2,'manifest':{'id':'package/ch5/special_reference','requires':['preset/ark_standard'],
        'metadata':{'source_locks':{str(SOURCE.relative_to(ROOT)):PIN},'builder_sha':sha(Path(__file__)),
            'variant_bindings':[],'status':'special_source_consumers_pending_peer','full_stage_executed':False,'client_verified':False,
            'policies':{'windup':'SourceOnAttackSeconds/effectiveASPD ratio min.01; duration animation unscaled. Explicit reference pending loader scaling',
                'hammerSP':'Once per accepted attack damage cast including skill; cost2 before firsthit, gate cooldown1 and sharedinterval3.5',
                'stun':'DB7seconds/sourceflag0 control applicability respects projected immunity',
                'lunmag':'Combat and Attack share samePPtr4029926580866268503, one ranged packet, SourceCombat2 currentblocker hardqualification',
                'projectile':'Source speed10/lifetime10 homing trace point; actual collider/camera awaiting user calibration'}}},
        'entities':[],'abilities':[],'selectors':[],'behaviors':[],'buffs':[], 'projectiles':[], 'rules':rules}
    for key in ('enemy_1045_hammer','enemy_1038_lunmag'):
        variant=next(v for v in source['variants'].values() if v['native_enemy']['native_id']==key)
        db=variant['native_enemy']['resolved'];a=db['attributes'];prefab=source['prefabs'][variant['prefab_key']]
        root=next(c['raw'] for c in prefab['components'].values() if c['native_class']=='Enemy')
        mover=next(c['raw'] for c in prefab['components'].values() if c['native_class']=='MoveController')
        mode=variant['modes'][0];raw=mode['nodes']['_combat']['raw'];anim=mode['nodes']['_combat']['animation_binding']
        assert len(variant['modes'])==1 and raw['_selectTargetSource']==2 and raw['_damageType']==(1 if key.endswith('hammer') else 2)
        if key.endswith('lunmag'):assert mode['raw']['_combat']==mode['raw']['_attack']
        frame=next(e['frame'] for e in anim['events'] if e['name']=='OnAttack');assert frame==(28 if key.endswith('hammer') else 21)
        uid='unit/'+prefix+'/'+key;aid='ability/'+prefix+'/'+key+'/normal';sid='selector/'+prefix+'/'+key
        components={'attributes':{'base':{'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],
                'move_speed':a['moveSpeed'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,
                'mass_level':a['massLevel'],'block_cost':root['_blockVolume']}},
            'resources':{'hp':{'initial':a['maxHp'],'capacity_attribute':'max_hp','role':'health'}},
            'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},
            'spatial':{'motion_mode':0,'steering':{'rule':'rule/'+prefix+'/steering','parameters':{
                'response_factor':mover['_steeringFactor'],'max_acceleration':mover['_maxSteeringForce'],'arrival_radius':.05}}},
            'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':db['lifePointReduce']},'abilities':[aid],
            'behavior':{'machine':'behavior/'+prefix+'/'+key}}
        selector={'id':sid,'kind':'selector','filters':[{'tag':'player'},{'state':'alive'}],'limit':1}
        effect={'op':'damage','damage_type':'physical' if key.endswith('hammer') else 'arts','scale':1,
            'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False},
            'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}
        ability={'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},
            'rules':{'ability.windup':'rule/'+prefix+'/windup','targeting.score':'rule/'+prefix+'/score'},
            'duration_seconds':anim['duration']['seconds'],'timeline':[{'at_seconds':frame/30,'effect':effect}]}
        if key.endswith('hammer'):
            assert db['spData']=={'spType':'INCREASE_WHEN_ATTACK','maxSp':2,'initSp':0,'increment':1.0}
            components['resources']['sp']={'initial':0,'capacity':2}
            ability['activation']['parameters'].update(sp_resource='sp',recovery_per_attack=1)
            selector['region']={'type':'all','blocked_only':True}
            stunid='buff/'+prefix+'/hammer_stun';skill=deepcopy(ability);skillid=aid.replace('/normal','/stun')
            skill.update(id=skillid,initial_cooldown_seconds=1,cooldown_seconds=1)
            skill['activation']={'mode':'manual','costs':[{'resource':'sp','amount':2}],
                'forbidden_source_flags':[0,12],'parameters':{'auto_only':True,'requires_targets':True,
                    'replace_attack':True,'sp_resource':'sp','recovery_per_attack':1}}
            skill['timeline'][0]['effect']['on_success']=[{'op':'apply_buff','buff':stunid}]
            p['buffs'].append({'id':stunid,'kind':'buff','duration_seconds':7,'selection_flags':{'abnormal_flags':[0]},
                'control_rule':'rule/'+prefix+'/stun','control':{'move':False,'attack':False,'abilities':False,'block':False,'interrupt':True}})
            p['abilities'].append(skill);components['abilities'].insert(0,skillid)
            components['ability_arbitration']={'priority_order':'higher_first','busy':'all_casts','entries':[
                {'ability':ident,'priority':priority,'attack_clock':True,'require_attack_control':True,'condition':'True','parameters':{}}
                for ident,priority in [(skillid,0),(aid,-1)]]}
        else:
            native=next(c['raw'] for c in prefab['components'].values() if c['native_class']=='AdvancedSelector')
            defaults={'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],'abnormal_combos':[],
                'target_free_flags':[],'target_free_combos':[],'target_free':False,'ally_target_free':False,'heal_free':False,
                'camouflage':False,'can_select_camouflage':False}
            selector.update(region={'type':'radius','radius':db['rangeRadius']},eligibility={'rule':'rule/'+prefix+'/combat_guard',
                'parameters':{'source_configuration':native,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}})
            projectile=source['projectiles']['projectile_lunmag'];mov=next(c['raw'] for c in projectile['components'].values() if c['native_class']=='AdvancedMovement')
            spec=next(c['raw'] for c in projectile['components'].values() if c['native_class']=='SimpleProjectile')
            assert mov['_speed']==10 and spec['_lifeTime']==10
            projid='projectile/'+prefix+'/lunmag';effect['projectile_definition']=projid
            p['projectiles'].append({'id':projid,'kind':'projectile','motion':{'rule':'rule/'+prefix+'/trajectory','parameters':{'mode':'homing','speed':10}},
                'collision':{'rule':'rule/'+prefix+'/collision','parameters':{'enabled':True,'radius':0}},'lifetime_seconds':10,
                'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,
                'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'cancel','target_hidden':'cancel',
                    'finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True},'on_invalid':[]})
        p['entities'].append({'id':uid,'kind':'entity','tags':['enemy','ground'],'metadata':{'native_variant_id':variant['variant_id']},'components':components})
        p['abilities'].append(ability);p['selectors'].append(selector)
        p['behaviors'].append({'id':'behavior/'+prefix+'/'+key,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],
            'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':sid}],
                'cast_groups':[{'key':'combat','abilities':components['abilities']}],
                'parameters':{'target_key':'normal','blocked_target':True,'stop_on_target':False if key.endswith('hammer') else True,'stop_cast_groups':['combat']}}]}})
        p['manifest']['metadata']['variant_bindings'].append({'variant_id':variant['variant_id'],'unit_definition':uid,
            'source_node':mode['nodes']['_combat'],'source_attack_slot':mode['raw']['_attack'],'source_spData':db.get('spData'),'source_skills':db.get('skills'),
            'source_frame':frame,'attributes':a})
    return p
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:assert OUT.read_bytes()==raw
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        with OUT.open('xb') as f:f.write(raw)
    print(json.dumps({'sha':hashlib.sha256(raw).hexdigest(),'units':2,'full_stage_executed':False}))
if __name__=='__main__':main()
