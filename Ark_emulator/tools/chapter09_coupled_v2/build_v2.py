"""Source-owned duholy/dushdo pair on frozen joint V6; no DB-only Flame grant."""
import json,hashlib,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_foundation_v6_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.domains.selection import DEFAULT_STATE,eligibility_profile
CORE='a8a22012563653020b3e7cce311128f3147f1cb88a1769f9abd8d9bb6d376c03'
SOURCE=ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json';DETAIL=SOURCE.with_name('source.detail.v1.json');FREEZE=SOURCE.with_name('source.freeze.v2.json')
OUT=ROOT/'packages/campaign/chapter09_consumers/coupled_v2';TEMPLATE=ROOT/'packages/campaign/chapter09_consumers/ordinary/enemy_1165_duhond.module.v1.json'
NAMES={'duholy':'enemy_1174_duholy','dushdo':'enemy_1175_dushdo'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def live(rows,key,now):return any(x['definition']==key and x.get('applicability',{}).get('active',True) and (x['expires_at'] is None or now<x['expires_at']) for x in rows)
def marker_eligibility(inputs,params,context):
    if inputs['source']['id']==inputs['candidate']['id']:return {'accepted':False,'reason':'source_excluded'}
    source={**inputs['selection_states']['source'],'can_select_invisible':params['partner_detect_invisible']}
    decision=eligibility_profile({**inputs,'selection_states':{**inputs['selection_states'],'source':source}},{},context)
    if not decision['accepted']:return decision
    accepted=live(inputs['candidate']['components'].get('buffs',{}).get('instances',[]),params['required_buff'],context['time'])
    return {'accepted':accepted,'reason':'required_live_partner_marker' if accepted else 'partner_marker_absent'}
def held_unless_trigger(inputs,params,context):
    return not live(inputs['owner']['components'].get('buffs',{}).get('instances',[]),params['required_buff'],context['time'])
def providers():return {**BUILTIN_PROVIDERS,'reference.c9.coupled.marker':{'callable':marker_eligibility,'version':'2'},'reference.c9.coupled.trigger_held':{'callable':held_unless_trigger,'version':'2'}}
def replace(value,old,new):
    if isinstance(value,dict):return {k:replace(v,old,new) for k,v in value.items()}
    if isinstance(value,list):return [replace(v,old,new) for v in value]
    if isinstance(value,str):return value.replace(old,new)
    return value
def rule(id,contract,expression=None,provider=None,parameters=None):
    return {'id':id,'kind':'calculation_rule','contract':contract,'implementation':{'type':'provider','provider':provider} if provider else {'type':'expression','expression':expression},**({'parameters':parameters} if parameters is not None else {})}
def lease():return {'mode':'shared','identity':['definition','target'],'source_binding':'oldest_live_lease','external_child_collision':'reject'}
def cfg(options):
    result={'_'+k:v for k,v in options.items()};result.update(_forceIgnoreCamouflage=0,_needProfessionMask=0);return result
def selector(id,configuration,radius=None,ruleid='rule/ch9/coupled/eligible',blocked=False):
    return {'id':id,'kind':'selector','region':{'type':'all','blocked_only':True} if blocked else {'type':'radius','radius':radius},'filters':[{'state':'alive'}],**({'limit':1} if blocked else {}),'eligibility':{'rule':ruleid,'parameters':{'source_configuration':configuration,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}}}
def build(*,radius_profile='native_collider',partner_detect_invisible=True,required_skill_policy='owned_native_components_only'):
    assert implementation_digest()==CORE
    if radius_profile not in ('native_collider','trait_blackboard'):raise ValueError('Unknown explicit radius reference profile')
    if type(partner_detect_invisible) is not bool:raise ValueError('Partner visibility profile must be strict bool')
    if required_skill_policy not in ('owned_native_components_only','all_db_rows'):raise ValueError('Unknown required skill policy')
    native=json.loads(SOURCE.read_bytes());detail=json.loads(DETAIL.read_bytes());template=json.loads(TEMPLATE.read_bytes())
    bson=native['bson_templates']['templates']['enemy_dushdo_duholy_trigger'];assert not native['bson_templates']['native_method_bodies_recovered']
    package={'schemaVersion':2,'manifest':{'id':'package/ch9/coupled/native_v2','requires':['preset/ark_standard'],'metadata':{'required_runtime':CORE,'source_locks':{str(p):sha(p) for p in (SOURCE,DETAIL,FREEZE,TEMPLATE,Path(__file__))},'reference_profiles':{'radius':radius_profile,'partner_detect_invisible':partner_detect_invisible,'trait_lifecycle':'shared first acquisition/last release toggles owned trait bundle; current incoming buff excluded in native start-check reference','dushdo_timing':'sample at cast; multiply authored hit/full seconds by min(1,current_attack_interval/native_cycle); next_attack sampled at this same cast and not retroactively rescheduled'},'required_skill_policy':required_skill_policy,'native_method_body_verified':False,'bson_trigger':bson,'native_closures':{},'unused_db_rows':{},'full_db_skill_closure_supported':False,'whole_stage_executed':False,'independent_reviewed':False,'client_verified':False}},'entities':[],'buffs':[],'abilities':[],'selectors':[],'behaviors':[],'rules':[rule('rule/ch9/coupled/eligible','targeting.eligibility',provider='model.targeting.eligibility')]}
    for name,key in NAMES.items():
        vid,row=next((k,v) for k,v in native['variants'].items() if v['prefab_key']==key);prefab=native['prefabs'][key];components=prefab['components'];mode=row['modes'][0];combat=mode['nodes']['_combat'];root=next(c for c in components.values() if c['native_class']=='Enemy');mover=next(c for c in components.values() if c['native_class']=='MoveController');stats=row['native_enemy']['resolved']['attributes'];bb={x['key']:x['value'] for x in row['native_enemy']['resolved']['talentBlackboard']}
        assert not root['raw']['_commonAbilities'] and not mode['raw']['_generalAbilities'];assert len(row['modes'])==1
        assert combat['native_class']=='MeleeAttack' and combat['raw']['_damageType']==(1 if name=='duholy' else 2)
        skill_components=[c for c in components.values() if 'Skill' in c['native_class']]
        db_skills=row['native_enemy']['resolved'].get('skills') or []
        if db_skills and not skill_components:
            package['manifest']['metadata']['unused_db_rows'][key]={'rows':db_skills,'reason':'No owned native skill component; root commonAbilities and mode generalAbilities are empty. DB Flame is not granted by this consumer.','native_component_classes':sorted(c['native_class'] for c in components.values())}
            if required_skill_policy=='all_db_rows':raise ValueError(key+': full DB Flame requirement has no proven owned native component')
        prefix='ch9/coupled/'+name;part=replace(deepcopy(template),'ch9/duhond',prefix)
        unit=part['entities'][0];unit['id']='unit/'+prefix+'/'+vid.split('/')[-1];unit['metadata']={'native_variant':vid,'native_reference':row['native_reference']};body=unit['components'];base=body['attributes']['base']
        base.update(max_hp=stats['maxHp'],atk=stats['atk'],**{'def':stats['def'],'mres':stats['magicResistance']},move_speed=stats['moveSpeed'],attack_interval=stats['baseAttackTime'],attack_speed_ratio=stats['attackSpeed']/100,mass_level=stats['massLevel'],block_cost=root['raw']['_blockVolume'])
        if 'tauntLevel' in stats:base['taunt_level']=stats['tauntLevel']
        body['resources']['hp']['initial']=stats['maxHp'];body['spatial']['steering']['parameters'].update(response_factor=mover['raw']['_steeringFactor'],max_acceleration=mover['raw']['_maxSteeringForce'])
        animation=combat['animation_binding'];hit=next(e for e in animation['events'] if e['name']=='OnAttack');ability=part['abilities'][0];ability['duration_seconds']=animation['duration']['seconds'];ability['timeline'][0]['at_seconds']=hit['seconds'];ability['timeline'][0]['effect']['damage_type']='physical' if name=='duholy' else 'arts';ability['metadata']={'source_OnAttack_frame':hit['frame'],'source_full_frame':animation['duration']['frame'],'source_combat':combat}
        part['buffs']=[];body['buffs']['initial']=[]
        if name=='duholy':
            raw_buff=next(b for x in row['passive_and_skill_components'] for b in x['raw'].get('_buffs',[]) if isinstance(b,dict) and b['buffKey']=='enemy_refracting');part['buffs'].append({'id':'buff/'+prefix+'/refracting','kind':'buff','stacking':{'mode':'refresh','max_stacks':1},'modifiers':[{'attribute':'mres','layer':'flat','value':bb['refracting.magic_resistance']}],'active_rule':'rule/'+prefix+'/not_silenced','metadata':{'native_inline':raw_buff}});body['buffs']['initial'].append('buff/'+prefix+'/refracting')
        else:
            assert not any(b.get('buffKey')=='enemy_refracting' for x in row['passive_and_skill_components'] for b in x['raw'].get('_buffs',[]) if isinstance(b,dict))
            for r in part['rules']:
                if r['contract'] in ('ability.windup','ability.duration'):r['implementation']['expression']='inputs.'+('timing_parameters' if r['contract']=='ability.windup' else 'duration_parameters')+'.seconds * min(1, inputs.attributes.attack_interval / params.native_cycle) / max(inputs.attributes.attack_speed_ratio,.01)';r['parameters']={'native_cycle':stats['baseAttackTime']}
        combat_cfg=cfg({'targetSide':2,'targetMotion':1,'targetCategory':1,'ignoreTargetFree':0,'onlyIgnoreSomeOfTargetFreeCase':0,'abnormalFlag':0,'abnormalCombo':0,'ignoreAllyTargetFree':0,'ignoreHealFree':0,'ignoreMotionMode':0,'excludeSomeAbnormalFlags':0,'excludeAbnormalFlag':0,'professionMask':0,'checkUnitType':0,'unitTypeMask':0})
        part['selectors'][0]=selector(part['selectors'][0]['id'],combat_cfg,blocked=True)
        marker='buff/'+prefix+'/mask';marker_raw=next(b for x in row['passive_and_skill_components'] for b in x['raw'].get('_buffs',[]) if isinstance(b,dict) and b['buffKey']==name+'_mask');part['buffs'].append({'id':marker,'kind':'buff','metadata':{'native_inline':marker_raw}});body['buffs']['initial'].append(marker)
        aura=next(x for x in row['passive_and_skill_components'] if x['class']=='AuraAbility' and x['raw']['_buffs'][0]['templateKey']=='enemy_dushdo_duholy_trigger');validator=components[str(aura['raw']['_targetValidator']['m_PathID'])];geo=next(g for g in prefab['geometry_sources'] if g['unity_type']=='CircleCollider2D' and g['gameobject_path_id']==aura['raw']['m_GameObject']['m_PathID']);assert geo['raw']['m_Radius']==1 and aura['raw']['_selfOption']==2
        other='dushdo' if name=='duholy' else 'duholy';to_partner='buff/ch9/coupled/'+other+'/trigger';own_trigger='buff/'+prefix+'/trigger';parent='buff/'+prefix+'/partner_aura';sid='selector/'+prefix+'/partner';rkey='rule/'+prefix+'/partner'
        part['selectors'].append(selector(sid,cfg(validator['raw']['_targetOptions']),1,rkey));part['rules'].append(rule(rkey,'targeting.eligibility',provider='reference.c9.coupled.marker',parameters={'required_buff':'buff/ch9/coupled/'+other+'/mask','partner_detect_invisible':partner_detect_invisible}))
        part['buffs'].append({'id':parent,'kind':'buff','aura':{'selector':sid,'buff':to_partner,'lease_policy':lease()},'metadata':{'native_aura':aura,'native_validator':validator,'native_geometry':geo}});body['buffs']['initial'].append(parent)
        part['buffs'].append({'id':own_trigger,'kind':'buff','stacking':{'mode':'refresh','identity':['definition','target'],'max_stacks':1},'effects':[{'op':'emit','event':'coupled.trait.started','payload':{'trait_owner_role':'target','native_wrapper':'traitAbility'}}],'on_remove':[{'op':'emit','event':'coupled.trait.finished','payload':{'trait_owner_role':'target','native_wrapper':'traitAbility'}}],'metadata':{'native_template':'enemy_dushdo_duholy_trigger','native_bson_sha256':bson['document_sha256'],'semantic_binding':'first shared child activates owner trait; last lease release deactivates owner trait; query checks are by exact live definition, no buff-list index'}})
        trait='buff/'+prefix+'/trait';toggle='buff/'+prefix+'/trait_owner';held='rule/'+prefix+'/trait_held';part['rules'].append(rule(held,'passive.toggle',provider='reference.c9.coupled.trigger_held',parameters={'required_buff':own_trigger}));part['buffs'].append({'id':toggle,'kind':'buff','toggle':{'rule':held,'buff':trait,'initial_enabled':True,'restore_delay_seconds':0,'events':[]}});body['buffs']['initial'].append(toggle)
        if name=='duholy':
            target_aura=next(x for x in row['passive_and_skill_components'] if x['class']=='AuraAbility' and x['raw']['_buffs'][0]['buffKey']=='duholy_auraAbility');target_validator=components[str(target_aura['raw']['_targetValidator']['m_PathID'])];tgeo=next(g for g in prefab['geometry_sources'] if g['unity_type']=='CircleCollider2D' and g['gameobject_path_id']==target_aura['raw']['m_GameObject']['m_PathID']);assert tgeo['raw']['m_Radius']==1
            radius=1 if radius_profile=='native_collider' else bb['traitAbility.range_radius'];slow='buff/'+prefix+'/aspd_down';sid='selector/'+prefix+'/players'
            part['selectors'].append(selector(sid,cfg(target_validator['raw']['_targetOptions']),radius));part['buffs'].append({'id':slow,'kind':'buff','stacking':{'mode':'refresh','identity':['definition','target'],'max_stacks':1},'modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':bb['traitAbility.attack_speed']/100}],'metadata':{'native_inline':target_aura['raw']['_buffs'][0]}})
            part['buffs'].append({'id':trait,'kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'taunt_level','layer':'flat','value':bb['traitAbility.taunt_level']}],'aura':{'selector':sid,'buff':slow,'lease_policy':lease()},'metadata':{'native_wrapper':next(c for c in components.values() if c['native_class']=='ActiveAbilityWrapper'),'source_radius_collider':1,'source_radius_blackboard':bb['traitAbility.range_radius'],'selected_radius':radius,'trait_taunt_bonus':bb['traitAbility.taunt_level']}})
        else:
            part['buffs'].append({'id':trait,'kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'attack_interval','layer':'flat','value':bb['traitAbility.base_attack_time']}],'metadata':{'native_wrapper':next(c for c in components.values() if c['native_class']=='ActiveAbilityWrapper'),'native_cycle':stats['baseAttackTime']}})
            checker=next(c for c in components.values() if c['native_class']=='AdvancedCompoundToggleChecker');invis=next(x for x in row['passive_and_skill_components'] if x['class']=='ToggleablePassiveBuffAbility');child='buff/'+prefix+'/invisible';toggle='buff/'+prefix+'/invisible_owner';ruleid='rule/'+prefix+'/invisible_held'
            assert checker['raw']['_isInitToggled']==checker['raw']['_disableWhenAttack']==checker['raw']['_disableWhenBlocked']==1 and checker['raw']['_restoreDelay']==3
            part['rules'].append(rule(ruleid,'passive.toggle','inputs.blocker_active'));part['buffs'].extend([{'id':child,'kind':'buff','stacking':{'mode':'independent'},'selection_flags':{'abnormal_flags':[9]},'metadata':{'native_inline':invis['raw']['_buffs'][0]}},{'id':toggle,'kind':'buff','toggle':{'rule':ruleid,'buff':child,'initial_enabled':True,'restore_delay_seconds':3,'events':[{'event':'ability.started','owner_role':'source','condition':'inputs.payload.ability == params.combat'}],'parameters':{'combat':ability['id']}},'metadata':{'native_toggle':invis,'native_checker':checker}}]);body['buffs']['initial'].append(toggle)
        for field in ('entities','buffs','abilities','selectors','behaviors','rules'):package[field].extend(part[field])
        package['manifest']['metadata']['native_closures'][key]={'variant':row,'prefab':prefab,'detail':detail['blackboard_prefixes_and_raw_rows'][vid],'owned_native_skill_components':skill_components,'mode_and_root_ability_ownership_proven':True}
    fixture=deepcopy(package);fixture['scenarioDraft']={'id':'scene/ch9/coupled_compile','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':3},'initialEntities':[{'definition':u['id'],'position':{'row':i,'col':0}} for i,u in enumerate(package['entities'])]};Compiler(providers=providers()).compile(fixture)
    return package
if __name__=='__main__':
    p=build();OUT.mkdir(parents=True,exist_ok=True);path=OUT/'duholy_dushdo.module.v2.json';path.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(str(path),sha(path))
