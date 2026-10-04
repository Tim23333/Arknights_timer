from tools.experiments.chapter02_twelve_peer.test_guard import ROOT,module,binding,defn,Compiler,Engine,replay
from copy import deepcopy
import json,pytest
from tools.build_mainline_dependencies import resolve_enemy,DEFAULT_DB

def test_module_actual_table_attributes_and_overrides_equal_independent_resolve():
    p=module();native=json.loads((ROOT/'packages/campaign/native_reference/level_main_02-10.json').read_bytes());db=json.loads(DEFAULT_DB.read_bytes())
    rows=p['manifest']['metadata']['variant_bindings'];assert sum(row['spawn_count'] for row in rows)==36 and len(rows)==12
    for ref in native['enemyDbRefs']:
        row=next(x for x in rows if x['native_reference']==ref);resolved=resolve_enemy(db,ref)['resolved'];u=defn(p,row['unit_definition']);base=u['components']['attributes']['base']
        for key,value in [('maxHp','max_hp'),('atk','atk'),('def','def'),('magicResistance','mres'),('moveSpeed','move_speed'),('baseAttackTime','attack_interval')]:assert base[value]==resolved['attributes'][key]
        assert base['attack_speed_ratio']==resolved['attributes']['attackSpeed']/100
        assert u['components']['lifecycle']['leak_loss']==resolved['lifePointReduce']
        assert u['components']['spatial']['motion_mode']==(1 if resolved['motion']=='FLY' else 0)

def cross_scene():
    p=module();row=binding(p,'enemy_1018_aoemag');enemy=row['unit_definition']
    target={'id':'unit/peer/player','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':5000,'def':0,'mres':30,'block_count':0}},
        'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'selection_state':{'side':0,'motion':2,'category':1}}}
    ground=deepcopy(target);ground['id']='unit/peer/ground';ground['components']['selection_state']['motion']=1;p['definitions'] += [target,ground]
    pos=[('main',3,4),('north',2,4),('south',4,4),('east',3,5),('west',3,3),('diagonal',4,5),('twoaway',3,6)]
    p['scenarioDraft']={'id':'scene/peer/cross','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':7,'cols':8},'initialEntities':[
        {'definition':enemy,'instanceAlias':'enemy','position':{'row':3,'col':2}},
        *[{'definition':'unit/peer/ground' if name=='main' else 'unit/peer/player','instanceAlias':name,'position':{'row':r,'col':c}} for name,r,c in pos]]}
    return p

def test_actual_aoemag_specified_frame21_cross5_vs_spine24_and_RES30():
    p=cross_scene();program=Compiler().compile(p);s=Engine.create(program,seed=4820);s.advance(23)
    packets=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(packets)==5 and all(e['time']==21 for e in packets)
    assert {e['payload']['target'] for e in packets}=={s.session.world.resolve(x) for x in ('main','north','south','east','west')}
    assert all(e['payload']['amount']==pytest.approx(240*.7) for e in packets)
    assert s.ctx.resources.current('diagonal','hp')==5000 and s.ctx.resources.current('twoaway','hp')==5000
    assert s.snapshot()==replay(program,s.export_replay()).snapshot()

def test_default_reference_primary_radius_accepts_real_distance2point15():
    p=cross_scene();p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:2]
    p['scenarioDraft']['initialEntities'][1]['position']={'row':3,'col':4.15}
    p['scenarioDraft']['initialEntities'][0]['components']={'attributes':{'base':{'move_speed':0}}}
    s=Engine.create(Compiler().compile(p));s.advance(23);assert s.ctx.resources.current('main','hp')==pytest.approx(5000-168)

def test_source_mode_mob_and_mob2_same_frame_different_DB_damage_without_fixture_target_copy():
    p=module();units=[binding(p,name)['unit_definition'] for name in ('enemy_1027_mob','enemy_1027_mob_2')]
    target={'id':'unit/peer/hold','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':8000,'def':25,'mres':0,'block_count':1}},
        'resources':{'hp':{'initial':8000,'capacity':8000,'role':'health'}},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}}}
    p['definitions'].append(target)
    p['scenarioDraft']={'id':'scene/peer/variants','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':3},'initialEntities':[
        {'definition':u,'instanceAlias':'enemy'+str(i),'position':{'row':i*2,'col':0},'route':{'motionMode':0,'startPosition':{'row':i*2,'col':0},'endPosition':{'row':i*2,'col':2},'checkpoints':[]}}
        for i,u in enumerate(units)]+[{'definition':target['id'],'instanceAlias':'target'+str(i),'position':{'row':i*2,'col':0}} for i in range(2)]}
    s=Engine.create(Compiler().compile(p));s.advance(14);packets=[e for e in s.session.events if e['type']=='damage.accepted']
    assert sorted(e['payload']['amount'] for e in packets)==[225,325] and [e['time'] for e in packets]==[13,13]

def test_three_input_target_components_are_actual_raw_Unity_nodes_not_metadata_only():
    import UnityPy
    native=json.loads((ROOT/'packages/campaign/chapter02_sources/native.reference.json').read_bytes());p=module();cache={}
    for name in ('enemy_1011_wizard','enemy_1028_mocock','enemy_1018_aoemag'):
        bound=binding(p,name);v=native['variants'][bound['variant_id']];prefab=native['prefabs'][v['prefab_key']];path=ROOT.parent/prefab['source']['path']
        if path not in cache:cache[path]={o.path_id:o for o in UnityPy.load(str(path)).objects}
        for mode in v['modes']:
            node=mode['nodes']['_combat'];assert node['native_class']==('MeleeAttack' if name=='enemy_1018_aoemag' else 'RangedAttack')
            actual=cache[path][node['path_id']].read_typetree();assert actual==node['raw'] and actual['_selectTargetSource']==2
