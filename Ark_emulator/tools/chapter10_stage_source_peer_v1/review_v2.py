"""Independent typed static audit of actual source-stage V2, no simulation."""
import json,hashlib,copy,traceback,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.chapter10_stage_source_peer_v1.source_preflight import exact,expected_route,source,PLAN,ROOT
PACKAGE=ROOT/'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v2.life99999.json'
ROSTER=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json'
OUT=ROOT/'validation/campaign/chapter10_stage_source_peer_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
p=load(PACKAGE);meta=p['manifest']['metadata'];scene=p['scenarioDraft'];defs={d['id']:d for d in p['definitions']};native=load(PLAN)['stages']['level_main_10-14']['native_document'];FACT={}
def full_source():
    exact(meta['native_document'],native);exact(scene['metadata']['native_options'],native['options']);exact(scene['metadata']['native_predefines'],native['predefines'])
    locks={path:sha(Path(path))==value for path,value in meta['source_locks'].items()};assert all(locks.values()),locks
    FACT['source_lock_count']=len(locks);FACT['full_native_document_typed_equal']=True
def scene_native():
    nw=native['waves'];sw=scene['timeline']['waves'];assert len(nw)==len(sw);births=0;controls=0;used=set()
    for wi,(a,b) in enumerate(zip(nw,sw)):
        for x,y in [('preDelay','pre_delay_seconds'),('postDelay','post_delay_seconds'),('maxTimeWaitingForNextWave','max_wait_seconds')]:exact(a[x],b[y],f'wave{wi}.{x}')
        assert len(a['fragments'])==len(b['fragments'])
        for fi,(nf,sf) in enumerate(zip(a['fragments'],b['fragments'])):
            exact(nf['preDelay'],sf['pre_delay_seconds']);assert len(nf['actions'])==len(sf['actions'])
            for ai,(na,sa) in enumerate(zip(nf['actions'],sf['actions'])):
                exact(na,sa['metadata']['native_action']);exact(na['count'],sa['count']);exact(na['preDelay'],sa['delay_seconds']);exact(na['interval'],sa['interval_seconds'])
                exact(na['managedByScheduler'],sa['managed']);exact(not na['dontBlockWave'],sa['blocks_wave']);exact(na['blockFragment'],sa['blocks_fragment'])
                if na['actionType']=='SPAWN':
                    assert sa['kind']=='spawn';births+=sa['count'];used.add(na['routeIndex']);spawn=sa['spawn'];r=expected_route(native['routes'][na['routeIndex']],9)
                    if any(c['type'] in ('DISAPPEAR','APPEAR_AT_POS') for c in r['checkpoints'] or []):
                        r['transition_policy']={'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}}
                    exact(r,spawn['route']);exact(r['startPosition'],spawn['position']);assert spawn['parameters']=={'native_wave':wi,'native_fragment':fi,'native_action_index':ai,'native_route_index':na['routeIndex']}
                    assert spawn['definition']==meta['native_bindings'][na['key']]['unit']
                    expected={'rule':'rule/m7_spawn_rectangle','stream':'spawn','sample_axes':['col','row'],'sample_zero_range':False,'offset':{'row':-r['spawnOffset']['y'],'col':r['spawnOffset']['x']},'random_range':{'row':r['spawnRandomRange']['y'],'col':r['spawnRandomRange']['x']}}
                    exact(expected,spawn['placement'])
                else:
                    assert na['actionType']=='DISPLAY_ENEMY_INFO' and sa['kind']=='control';controls+=1;definition=defs[sa['definition']];assert definition['ack_policy']=='immediate'
                    effects=definition['steps'][0]['effects'];assert len(effects)==1 and effects[0]['op']=='emit' and effects[0]['event']=='reference.enemy_info.observed'
                    exact(effects[0]['payload']['native_action'],na);exact(effects[0]['payload']['native_route'],native['routes'][na['routeIndex']])
    assert births==32 and len(used)==28 and controls==2
    exact(scene['resources']['dp'],{'initial':10,'capacity':99,'recovery_rate':1.0,'recovery':{'mode':'periodic','interval_seconds':1.0}})
    exact(scene['resources']['life'],{'initial':99999,'capacity':99999});assert scene['parameters']['deploy_capacity']==8
    for raw,policy in zip(native['runes'],scene['metadata']['rune_policy']):exact(raw,policy['raw']);assert policy['active'] is False
    assert len(scene['metadata']['rune_policy'])==3
    preset=load(ROOT/'../unpack_work/campaign_c10_joint_v1_candidate/ark_sim/content/presets/ark_standard.json')
    def find(value):
        if isinstance(value,dict):
            if value.get('id')=='rule/m9_living_transition':return value
            for v in value.values():
                result=find(v)
                if result:return result
        elif isinstance(value,list):
            for v in value:
                result=find(v)
                if result:return result
    assert find(preset)['implementation']['provider']=='ark.movement.living_transition'
    FACT['scene']={'births':births,'used_routes':len(used),'routes_retained_native':len(meta['native_document']['routes']),'DISPLAY_controls':controls,'DP':10,'slots':8,'base_life':99999,'EASY_inactive':True,'hidden_policy':'Source hide/appear translated to existing explicit m9_living_transition reference; source-native method body not recovered.'}
def map_and_predefine():
    buildable={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3};passable={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3};expected=[]
    for row in native['mapData']['map']:
        for index in row:
            tile=copy.deepcopy(native['mapData']['tiles'][index]);tile['buildableType']=buildable[tile['buildableType']];tile['passableMask']=passable[tile['passableMask']];tile.pop('playerSideMask',None);expected.append(tile)
    exact(expected,scene['map']['tiles']);assert scene['map']['rows']==9 and scene['map']['cols']==13
    registration=meta['native_registration']['records'];assert len(registration)==len(scene['initialEntities'])==1
    r=registration[0];exact(r['raw_native'],native['predefines']['tokenInsts'][0]);assert r['raw_native']['inst']['potentialRank']==0
    e=scene['initialEntities'][0];assert e['position']=={'row':8,'col':0} and e['facing']=='up' and e['registration_key']==r['registration_key'];exact(e['parameters']['native_instance'],r['raw_native'])
    speed=defs[scene['rules']['movement.speed']];assert speed['parameters']['multiplier']==.5 and speed['implementation']['expression']=='inputs.movement_parameters.base_speed * params.multiplier'
    path=defs[scene['rules']['movement.path']];assert path['parameters']=={'use_route_diagonal':True,'corner_cut':False}
    FACT['map_and_registration']={'all117_tiles_typed_equal':True,'raw_potential0_runtime_row8':True,'native_move_multiplier':.5,'native_diagonal_true_reference_cornercut_false':True,'hard_predefines_empty_source_preserved':meta['native_document']['hardPredefines']}
def fixed12_semantics():
    roster=load(ROSTER);old={d['id']:d for d in roster['definitions']};exact(scene['roster'],roster['manifest']['metadata']['roster']);assert len(scene['roster'])==12
    removed=set(old)-set(defs);assert removed=={'rule/campaign_draft_move_speed','rule/m7_diagonal_path'}
    receiver=load(ROOT/'packages/campaign/common_elemental_receivers/recipe.ally.current.v1.json')['receiver_template'];bodies=0;sp=0;skills=0;temporal=[]
    for id,value in old.items():
        if id in removed:continue
        expected=copy.deepcopy(value)
        if value['kind']=='entity':
            bodies+=1;attrs=expected['components'].get('attributes',{})
            if 'atk' in attrs.get('base',{}):
                original=attrs.get('attribute_rules',{}).get('atk',{}).get('attributes.effective') or attrs.get('rules',{}).get('attributes.effective') or expected.get('rules',{}).get('attributes.effective') or 'rule/ark_attribute_layers'
                rid='rule/ch10/remaining/atk/'+id.replace('/','_');attrs.setdefault('attribute_rules',{}).setdefault('atk',{})['attributes.effective']=rid
                assert defs[rid]['parameters']['base_rule']==original and original in defs[rid]['dependencies'];temporal.append({'entity':id,'original':original,'wrapper':rid})
            if expected['components'].get('selection_state',{}).get('side',0)==0:
                expected['components']['elemental']=copy.deepcopy(receiver)
                resource=expected['components'].get('resources',{}).get('sp')
                if resource is not None:
                    sp+=1;original=resource.get('recovery_freeze_rule') or resource.get('rules',{}).get('resource.recovery_freeze');rid='rule/campaign/elemental_receivers/freeze/'+id.replace('/','_');resource['recovery_freeze_rule']=rid
                    assert defs[rid]['parameters'].get('base_rule')==original and defs[rid]['dependencies']==([original] if original else [])
        elif value['kind']=='ability':
            skills+=1;activation=expected.get('activation',{})
            if activation.get('mode')=='manual' or activation.get('parameters',{}).get('replace_attack'):activation['forbidden_source_flags']=list(dict.fromkeys([*activation.get('forbidden_source_flags',[]),24]))
        exact(expected,defs[id],id)
    assert bodies==15
    FACT['fixed12']={'roster12_and_summons15_entities_preserved':True,'all_original_definitions_compared':len(old),'only_pruned_scene_path_rules':sorted(removed),'original_skills_compared':skills,'SP_freeze_compositions':sp,'original_effective_rule_chains':temporal}
def declaration_authority():
    changes=meta['explicit_definition_changes']
    for id,pair in changes.items():exact(pair['after'],defs[id],id+'.declared_after')
    for id,record in meta['raw_module_provenance'].items():
        if id in changes:assert changes[id]['before']['id']==id
        else:assert id in defs or id in meta['composition']['removed_ids'],id
    exact(sorted(set(meta['raw_module_provenance'])-set(defs)),sorted(meta['composition']['removed_ids']))
    raw_blood=load(ROOT/'packages/campaign/chapter10_consumers/bloodline/enemy_1220_dzoms.module.v1.json')
    mage=load(ROOT/'packages/campaign/chapter10_consumers/dkmage_source_v1/module.enemy_1225_dkmage_2.v1.json')
    blood={e['id']:e for e in raw_blood['entities']};matched=meta['raw_duplicate_actor_authority']['matched_raw'];assert set(matched)==set(blood)
    for e in mage['entities']:
        if e['id'] in blood:exact(e,blood[e['id']],e['id']+'.dedup')
    # Final control/eligibility tables must describe every actual retained Buff.
    actual={d['id']:{'flags':d.get('selection_flags',{}).get('abnormal_flags',[]),'immunes':d.get('selection_flags',{}).get('abnormal_immunes',[])} for d in defs.values() if d['kind']=='buff'}
    status=defs['rule/campaign/elemental_receivers/eligible']['parameters']['buff_flags']
    for id,v in actual.items():exact(v,status[id],id+'.receiver_flags')
    assert all('elemental' not in e['components'] for e in defs.values() if e['kind']=='entity' and e['components'].get('selection_state',{}).get('side',0)!=0)
    FACT['authority']={'typed_raw_mage_duplicate6_equal':True,'published_lord_wrapper_selected':meta['raw_duplicate_actor_authority']['authority'],'explicit_changes':len(changes),'actual_retained_buff_flags_checked':len(actual)}
def main():
    inputs=[PACKAGE,ROSTER,PLAN,Path(__file__),ROOT/'tools/chapter10_stage_assembly_v1/build.py',ROOT/'tools/chapter10_stage_assembly_v1/providers.py'];before={str(f):sha(f) for f in inputs};results=[]
    for f in [full_source,scene_native,map_and_predefine,fixed12_semantics,declaration_authority]:
        try:f();results.append({'case':f.__name__,'passed':True})
        except Exception as e:results.append({'case':f.__name__,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    after={str(f):sha(f) for f in inputs};code=0 if all(r['passed'] for r in results) and before==after else 1
    report={'schema':'ark-sim/source-stage-static-review/v1','actual_exit':code,'source_only_approved':code==0,'simulation_executed':False,'model_approved':False,'whole_stage_approved':False,'client_verified':False,'required_runtime':meta['required_runtime'],'source_before':before,'source_after':after,'source_equal':before==after,'results':results,'facts':FACT,'pending':meta['pending_model_gaps'],'self_authored_consumer_independently_approved':False}
    path=OUT/'source.review.v3.json';assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results,'report_sha256':sha(path)}));return code
if __name__=='__main__':raise SystemExit(main())
