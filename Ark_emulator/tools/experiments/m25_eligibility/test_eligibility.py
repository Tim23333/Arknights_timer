import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m25_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from ark_sim.adapters.api import implementation_digest
DEFAULTS={"side":0,"motion":1,"category":1,"profession":0,"unit_type":1,"abnormal_flags":[],"abnormal_combos":[],"target_free_flags":[],"target_free_combos":[],"target_free":False,"ally_target_free":False,"heal_free":False,"camouflage":False,"can_select_camouflage":False}
RAW=json.loads((ROOT/'validation/campaign/advanced_selector_source_audit.json').read_bytes())["actual_selectors"][0]["raw"]
def fixture():
    spec={"rule":"rule/eligibility","parameters":{"source_configuration":deepcopy(RAW),"side_policy":"relative_ally_enemy","neutral_policy":"reject","defaults":deepcopy(DEFAULTS)}}
    def actor(id,side,abilities=[]):
        return {"id":id,"kind":"entity","dependencies":["selector/probe"],"tags":["probe"],"components":{"selection_state":{"side":side},"spatial":{},"attributes":{"base":{"atk":10,"max_hp":100,"def":0}},"resources":{"hp":{"initial":100,"capacity":100,"role":"health"}},"abilities":abilities}}
    return {"entities":[actor("unit/source",1),actor("unit/target",0,["ability/free","ability/camo","ability/remove"])],"selectors":[{"id":"selector/probe","kind":"selector","region":{"type":"all"},"filters":[{"state":"alive"}],"eligibility":spec}],"rules":[{"id":"rule/eligibility","kind":"rule","contract":"targeting.eligibility","implementation":{"type":"provider","provider":"model.targeting.eligibility"}}],"buffs":[{"id":"buff/free","kind":"buff","duration_seconds":1,"selection_flags":{"abnormal_flags":[2]},"stacking":{"mode":"independent"}},{"id":"buff/camo","kind":"buff","duration_seconds":1,"selection_flags":{"abnormal_flags":[17]}}],"abilities":[{"id":"ability/"+name,"kind":"ability","activation":{"mode":"manual","on_start":[{"op":"apply_buff","buff":"buff/"+name,"target":"source"}]},"timeline":[]} for name in ("free","camo")]+[{"id":"ability/remove","kind":"ability","activation":{"mode":"manual","on_start":[{"op":"remove_buff","buff":"buff/free","target":"source"}]},"timeline":[]}],"scenarioDraft":{"id":"scenario/qualification","ruleset":"ruleset/ark_standard","objectives":{},"map":{"rows":3,"cols":3},"initialEntities":[{"definition":"unit/source","instanceAlias":"source","position":{"row":1,"col":0}},{"definition":"unit/target","instanceAlias":"target","position":{"row":1,"col":1}}]}}
def make(p=None):
    s=Engine.create(Compiler().compile(p or fixture()),seed=2501)
    assert Path(sys.modules['ark_sim'].__file__).resolve().parent==RUNTIME/'ark_sim'
    return s
def qualifies(s):
    before=s.checkpoint();result=s.ctx.spatial.qualifies('source','target',s.program.definitions['selector/probe']);assert s.checkpoint()==before;return result
def cp_replay(s):
    cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def config(p):return p['selectors'][0]['eligibility']['parameters']['source_configuration']
def state(p):return p['entities'][1]['components']['selection_state']
def test_live_free_half_open_public_commands():
    s=make();assert qualifies(s);s.submit({'action':'skill','source':'target','ability':'ability/free'},at=0);s.advance(1);assert not qualifies(s);s.advance(29);assert qualifies(s);cp_replay(s)
def test_camouflage_public_command_and_expiry():
    s=make();s.submit({'action':'skill','source':'target','ability':'ability/camo'},at=0);s.advance(1);assert not qualifies(s);s.advance(29);assert qualifies(s);cp_replay(s)
@pytest.mark.parametrize('name',['_abnormalFlag','_abnormalCombo','_excludeAbnormalFlag','_professionMask','_unitTypeMask'])
def test_inactive_invalid_fields_not_read(name):
    p=fixture();config(p)[name]={'not':'enum'};s=make(p);assert qualifies(s)
@pytest.mark.parametrize('flag', [0,5,24,44])
def test_other_abnormal_not_target_free(flag):
    p=fixture();state(p)['abnormal_flags']=[flag];assert qualifies(make(p))
@pytest.mark.parametrize('key,value,expected',[('motion',2,False),('category',2,False),('side',1,False),('side',2,False),('camouflage',True,False),('target_free',True,False)])
def test_typed_state_masks_and_flags(key,value,expected):
    p=fixture();state(p)[key]=value;assert qualifies(make(p)) is expected
@pytest.mark.parametrize('field,switch,value',[('_abnormalFlag','_onlyIgnoreSomeOfTargetFreeCase',46),('_abnormalCombo','_onlyIgnoreSomeOfTargetFreeCase',2),('_excludeAbnormalFlag','_excludeSomeAbnormalFlags',46),('_professionMask','_needProfessionMask',1024),('_unitTypeMask','_checkUnitType',8)])
def test_enabled_unknown_compile_rejected(field,switch,value):
    p=fixture();config(p)[switch]=1;config(p)[field]=value
    if switch=='_onlyIgnoreSomeOfTargetFreeCase':config(p)['_ignoreTargetFree']=1;config(p)['_abnormalFlag']=2;config(p)['_abnormalCombo']=0;config(p)[field]=value
    with pytest.raises(ValueError):Compiler().compile(p)
def test_foreign_contract_rejected():
    p=fixture();p['rules'][0]['contract']='damage.pipeline'
    with pytest.raises(ValueError,match='incompatible'):Compiler().compile(p)
def test_state_override_bad_enum_compile_rejected():
    p=fixture();p['scenarioDraft']['initialEntities'][1]['components']={'selection_state':{'abnormal_flags':[46]}}
    with pytest.raises(ValueError):Compiler().compile(p)
def test_force_camo_and_source_capability():
    for mode in ('force','source'):
        p=fixture();state(p)['camouflage']=True
        if mode=='force':config(p)['_forceIgnoreCamouflage']=1
        else:p['entities'][0]['components']['selection_state']['can_select_camouflage']=True
        assert qualifies(make(p))
def test_partial_target_free_causes_and_masks():
    p=fixture();config(p).update(_ignoreTargetFree=1,_onlyIgnoreSomeOfTargetFreeCase=1,_abnormalFlag=2,_abnormalCombo=0);state(p).update(target_free=True,target_free_flags=[2]);assert qualifies(make(p));state(p)['target_free_flags']=[2,4];assert not qualifies(make(p))
def test_union_remove_and_halfopen_readonly():
    s=make();s.submit({'action':'skill','source':'target','ability':'ability/free'},at=0);s.submit({'action':'skill','source':'target','ability':'ability/free'},at=10);s.advance(31);assert not qualifies(s);s.advance(9);assert qualifies(s);cp_replay(s)
def test_select_consumes_gate_before_rng():
    p=fixture();p['selectors'][0].update(ordering='random',limit=1,parameters={'random_stream':'imp'});state(p)['target_free']=True;s=make(p);before=s.session.random.snapshot();assert s.ctx.spatial.select('source','selector/probe')==[];assert s.session.random.snapshot()==before

def shot_fixture():
    p=fixture();p['entities'][0]['components']['abilities']=['ability/shot'];p['abilities'].append({'id':'ability/shot','kind':'ability','selector':'selector/probe','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'physical'}]},'timeline':[]});return p
def test_public_damage_gate_and_expiry_commands_replay():
    s=make(shot_fixture());s.submit({'action':'skill','source':'target','ability':'ability/free'},at=0);s.submit({'action':'skill','source':'source','ability':'ability/shot'},at=1);s.submit({'action':'skill','source':'source','ability':'ability/shot'},at=31);s.advance(32);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['time']==31 and hits[0]['payload']['amount']==10;assert s.ctx.resources.current('target','hp')==90;cp_replay(s)
def test_profession_unit_mask_independent_enable():
    p=fixture();state(p).update(profession=512,unit_type=4);config(p).update(_needProfessionMask=1,_professionMask=512,_checkUnitType=1,_unitTypeMask=4);assert qualifies(make(p));config(p)['_unitTypeMask']=1;assert not qualifies(make(p));config(p).update(_checkUnitType=0,_professionMask=32);assert not qualifies(make(p))
def test_heal_free_only_healing_eligibility():
    p=fixture();state(p)['abnormal_flags']=[7];s=make(p);selector=s.program.definitions['selector/probe'];assert s.ctx.spatial.qualifies('source','target',selector);assert not s.ctx.spatial.qualifies('source','target',selector,{'parameters':{'healing':True}})
def test_custom_pure_rule_replaces_qualification():
    p=fixture();state(p)['target_free']=True;p['rules'][0]['implementation']={'type':'expression','expression':"{'accepted': True, 'reason': 'explicit_custom_profile'}"};assert qualifies(make(p))
def test_custom_invalid_decision_rejected_runtime():
    p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':"{'accepted': True, 'reason': 'bad', 'extra': 1}"};s=make(p)
    with pytest.raises(ValueError,match='strict'):qualifies(s)
def test_real_rule_failure_complete_atomic_rollback():
    p=shot_fixture();p['rules'][0]['implementation']={'type':'expression','expression':'1/0'};p['abilities'][-1]['activation']['on_start'].insert(0,{'op':'random','stream':'imp','probability':1,'on_success':[{'op':'modify_resource','resource':'hp','amount':-1,'target':'source'}]});s=make(p);before=s.checkpoint()
    with pytest.raises(Exception,match='zero|division'):s.ctx.abilities.start('source','ability/shot')
    assert s.checkpoint()==before
def test_no_config_path_ignores_new_state_without_invented_events():
    p=fixture();del p['selectors'][0]['eligibility'];p['rules']=[];state(p)['target_free']=True;s=make(p);before=s.checkpoint();assert s.ctx.spatial.qualifies('source','target',s.program.definitions['selector/probe']);assert s.checkpoint()==before

@pytest.mark.parametrize('who',['source','target'])
def test_retired_actor_never_eligible(who):
    p=fixture();p['abilities'].append({'id':'ability/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]},'timeline':[]});
    for actor in p['entities']:actor['components']['abilities'].append('ability/retire')
    s=make(p);s.submit({'action':'skill','source':who,'ability':'ability/retire'},at=0);s.advance(1);assert any(e['type']=='command.accepted' for e in s.session.events);assert not qualifies(s);cp_replay(s)
def test_empty_implicit_defaults_rejected_compile():
    p=fixture();p['selectors'][0]['eligibility']['parameters']['defaults']={}
    with pytest.raises(ValueError,match='complete typed'):Compiler().compile(p)
def test_unknown_status_not_stun_inferred_and_bool_distinct():
    p=fixture();state(p)['target_free']=1
    with pytest.raises(ValueError,match='bool'):Compiler().compile(p)
