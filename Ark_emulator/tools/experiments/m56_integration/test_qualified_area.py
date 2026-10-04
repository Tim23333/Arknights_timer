import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m56_chapter03_integrated_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim.domains.qualified_areas import qualified_cell_offsets
def state(side=0):return {'side':side,'motion':1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False}
def configuration():return {'_targetSide':2,'_targetMotion':3,'_targetCategory':1,'_ignoreTargetFree':0,'_onlyIgnoreSomeOfTargetFreeCase':0,'_excludeSomeAbnormalFlags':0,'_needProfessionMask':0,'_ignoreAllyTargetFree':0,'_ignoreHealFree':0,'_ignoreMotionMode':0,'_forceIgnoreCamouflage':1,'_checkUnitType':0}
def fixture():
    source={'id':'unit/source','kind':'entity','tags':['enemy'],'components':{'spatial':{},'selection_state':state(1),'attributes':{'base':{'atk':100}},'abilities':['ability/area']}}
    target={'id':'unit/target','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':state(),'attributes':{'base':{'max_hp':1000,'def':0,'mres':0}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}}}}
    params={'offsets':[[r,c] for r in (-1,0,1) for c in (-1,0,1)],'eligibility':{'rule':'rule/elig','parameters':{'source_configuration':configuration(),'defaults':state(),'side_policy':'relative_ally_enemy','neutral_policy':'reject'}}}
    return {'manifest':{'requires':['preset/ark_standard']},'entities':[source,target],'rules':[{'id':'rule/area','kind':'rule','contract':'area.members','dependencies':['rule/elig'],'parameters':params,'implementation':{'type':'provider','provider':'ark.area.qualified_cell_offsets'}},
        {'id':'rule/elig','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}}],
        'selectors':[{'id':'selector/main','kind':'selector','region':{'type':'all'},'filters':[{'tag':'primary'}],'limit':1}],
        'abilities':[{'id':'ability/area','kind':'ability','selector':'selector/main','activation':{'mode':'manual','on_start':[{'op':'area','center':'target','membership_rule':'rule/area','effects':[{'op':'damage','damage_type':'true'}]}]},'timeline':[]}],
        'scenarioDraft':{'id':'scene/qualified/area','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':6,'cols':6},'initialEntities':[
            {'definition':'unit/source','instanceAlias':'source','position':{'row':0,'col':0}},
            {'definition':'unit/target','instanceAlias':'main','tags':['player','primary'],'position':{'row':3,'col':3}},
            {'definition':'unit/target','instanceAlias':'other','position':{'row':4,'col':4}}]}}
def sim(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=5301)
def fire(s,at=0):s.submit({'action':'skill','source':'source','ability':'ability/area'},at=at)
def test_actual_grid_and_nested_eligibility_trace_both_targets():
    s=sim();fire(s);s.advance(1);assert s.ctx.resources.current('main','hp')==900 and s.ctx.resources.current('other','hp')==900
    c=[e for e in s.session.events if e['type']=='calculation' and e['payload']['calculation_id']=='area.members'];assert len(c)==1
    stages=c[0]['payload']['trace']['stages'];assert any(x.get('calculation_id')=='targeting.eligibility' for x in stages)
@pytest.mark.parametrize('patch',[{'target_free':True},{'category':2},{'side':1},{'side':2},{'motion':0}])
def test_source_option_rejections_are_consumed(patch):
    p=fixture();p['scenarioDraft']['initialEntities'][2]['components']={'selection_state':patch};s=sim(p);fire(s);s.advance(1)
    assert s.ctx.resources.current('main','hp')==900 and s.ctx.resources.current('other','hp')==1000
def test_only_camouflage_is_ignored_and_flight_is_allowed():
    p=fixture();p['scenarioDraft']['initialEntities'][2]['components']={'selection_state':{'camouflage':True,'motion':2}};s=sim(p);fire(s);s.advance(1);assert s.ctx.resources.current('other','hp')==900
def test_live_buff_half_open_targetfree_projection_and_commands_replay(tmp_path):
    p=fixture();p['buffs']=[{'id':'buff/free','kind':'buff','duration_seconds':.1,'selection_flags':{'target_free':True}}];p['scenarioDraft']['initialEntities'][2]['components']={'buffs':{'initial':['buff/free']}}
    program=Compiler().compile(p);s=Engine.create(program,seed=5302);fire(s,2);fire(s,3);s.advance(2);path=tmp_path/'cp.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(3);r.advance(3)
    assert s.ctx.resources.current('other','hp')==900 and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
@pytest.mark.parametrize('mutation',[lambda p:p['rules'][0]['parameters']['eligibility']['parameters']['defaults'].pop('side'),
    lambda p:p['rules'][0]['parameters']['eligibility']['parameters']['source_configuration'].update(_targetMotion=4),
    lambda p:p['rules'][0]['parameters'].update(unknown=1),
    lambda p:p['rules'][1].update(contract='movement.distance')])
def test_compile_configuration_and_wrong_contract_strict(mutation):
    p=fixture();mutation(p)
    with pytest.raises(ValueError):Compiler().compile(p)
def test_replacement_eligibility_rule_actually_filters():
    p=fixture();p['rules'][1]['implementation']={'type':'expression','expression':"{'accepted':False,'reason':'explicit alternate'}"};s=sim(p);fire(s);s.advance(1);assert s.ctx.resources.current('main','hp')==1000
def test_real_eligibility_rule_failure_restores_full_atomic_checkpoint():
    p=fixture();p['rules'][1]['implementation']={'type':'expression','expression':"{'accepted':1/0 > 0,'reason':'failed'}"};s=sim(p);before=s.checkpoint()
    with pytest.raises(Exception):s.ctx.effects.execute('source',['main'],p['abilities'][0]['activation']['on_start'][0])
    assert s.checkpoint()==before
def test_provider_missing_projection_is_explicit_error():
    with pytest.raises(ValueError,match='projection'):qualified_cell_offsets({'center_position':{'row':0,'col':0},'candidates':[],'parameters':{}},fixture()['rules'][0]['parameters'],{})

def test_ally_free_is_distinct_from_enemy_free_and_ignored_enum_is_not_read():
    p=fixture();cfg=p['rules'][0]['parameters']['eligibility']['parameters']['source_configuration'];cfg.update(_targetSide=1,_abnormalFlag=999,_abnormalCombo=999,_excludeAbnormalFlag=999)
    p['scenarioDraft']['initialEntities'][1]['components']={'selection_state':{'side':1}}
    p['scenarioDraft']['initialEntities'][2]['components']={'selection_state':{'side':1,'ally_target_free':True}}
    s=sim(p);fire(s);s.advance(1);assert s.ctx.resources.current('main','hp')==900 and s.ctx.resources.current('other','hp')==1000

def test_enabled_unknown_enum_is_rejected():
    p=fixture();p['rules'][0]['parameters']['eligibility']['parameters']['source_configuration'].update(_excludeSomeAbnormalFlags=1,_excludeAbnormalFlag=46)
    with pytest.raises(ValueError):Compiler().compile(p)

def test_projected_corner_deduplicates_offsets_without_random_draw():
    p=fixture();p['rules'][0]['parameters']['offsets'] += [[1,1],[1,1]]
    p['scenarioDraft']['initialEntities'][2]['position']={'row':4.5,'col':4}
    s=sim(p);before=s.session.random.snapshot()
    fire(s);s.advance(1);assert s.ctx.resources.current('other','hp')==1000
    # A repeated geometric cell cannot produce repeated damage.
    assert s.ctx.resources.current('main','hp')==900
    assert s.session.random.snapshot()==before
    assert not [e for e in s.session.events if e['type'].startswith('random.')]

@pytest.mark.parametrize('decision',["{'accepted':1,'reason':'bad'}","{'accepted':True,'reason':'ok','extra':0}"])
def test_custom_eligibility_output_is_strict_and_rolls_back(decision):
    p=fixture();p['rules'][1]['implementation']={'type':'expression','expression':decision};s=sim(p);before=s.checkpoint()
    with pytest.raises(Exception):s.ctx.effects.execute('source',['main'],p['abilities'][0]['activation']['on_start'][0])
    assert s.checkpoint()==before
