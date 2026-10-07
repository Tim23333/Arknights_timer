from pathlib import Path
import sys
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m51_deploy_payment_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def fixture():
    return {'entities':[{'id':'unit/custom_card','kind':'entity','tags':['player'],'components':{
        'spatial':{},'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},
        'deployable':{'base_cost':5,'capacity':0,'cooldown_seconds':0,'terrain':'ground','parameters':{'max_instances':10},'stock':{'resource':'cards','amount':1}}}}],
        'scenarioDraft':{'id':'scene/stock','ruleset':'ruleset/ark_standard','objectives':{},'roster':['unit/custom_card'],
            'map':{'rows':1,'cols':7},'resources':{'dp':{'initial':100,'capacity':100},'cards':{'initial':5,'capacity':5}}}}


def test_actual_public_deploy_five_cards_then_sixth_rejects_with_saved_replay(tmp_path):
    s=Engine.create(Compiler().compile(fixture()),seed=5010)
    for i in range(6):s.submit({'action':'deploy','definition':'unit/custom_card','alias':'c'+str(i),'position':{'row':0,'col':i}},at=i)
    s.advance(3);cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
    s.advance(4);r.advance(4)
    assert s.ctx.resources.current('system/battle','cards')==0
    results=[e for e in s.session.events if e['type'] in ('command.accepted','command.rejected')]
    assert [e['type'] for e in results]==['command.accepted']*5+['command.rejected']
    assert results[-1]['payload']['reason']=='insufficient deployment stock'
    assert len(s.session.world.entities())==6
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_failed_placement_and_dp_do_not_consume_stock_or_create_actor():
    s=Engine.create(Compiler().compile(fixture()));s.submit({'action':'deploy','definition':'unit/custom_card','position':{'row':0,'col':8}},at=0);s.advance(1)
    assert s.ctx.resources.current('system/battle','cards')==5 and s.ctx.resources.current('system/battle','dp')==100
    p=fixture();p['scenarioDraft']['resources']['dp']['initial']=0;s=Engine.create(Compiler().compile(p));s.submit({'action':'deploy','definition':'unit/custom_card','position':{'row':0,'col':1}},at=0);s.advance(1)
    assert s.ctx.resources.current('system/battle','cards')==5 and len(s.session.world.entities())==1


@pytest.mark.parametrize('patch',[{'amount':True},{'amount':.5},{'amount':0},{'resource':'missing'},{'rule':'selector/missing'}])
def test_invalid_or_missing_stock_rejected_before_execution(patch):
    p=fixture();p['entities'][0]['components']['deployable']['stock'].update(patch)
    with pytest.raises(ValueError):Compiler().compile(p)


def test_withdrawal_does_not_silently_replenish_card_stock():
    s=Engine.create(Compiler().compile(fixture()));s.submit({'action':'deploy','definition':'unit/custom_card','alias':'one','position':{'row':0,'col':1}},at=0)
    s.submit({'action':'withdraw','source':'one'},at=1);s.advance(2)
    assert s.ctx.resources.current('system/battle','cards')==4
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_same_battle_resource_cost_and_stock_cannot_overspend_and_rolls_back():
    p=fixture();p['entities'][0]['components']['deployable']['stock']={'resource':'dp','amount':1};p['scenarioDraft']['resources']['dp']['initial']=5
    s=Engine.create(Compiler().compile(p));s.submit({'action':'deploy','definition':'unit/custom_card','position':{'row':0,'col':1}},at=0);s.advance(1)
    assert s.ctx.resources.current('system/battle','dp')==5 and len(s.session.world.entities())==1
    assert [e['type'] for e in s.session.events if e['type'].startswith('command.')]==['command.rejected']


def test_custom_stock_cost_rule_changes_quantity_without_kernel_edit():
    p=fixture();p['rules']=[{'id':'rule/two_cards','kind':'rule','contract':'resource.cost','implementation':{'type':'expression','expression':'inputs.cost_parameters.amount * 2'}}]
    p['entities'][0]['components']['deployable']['stock']['rule']='rule/two_cards'
    s=Engine.create(Compiler().compile(p));s.submit({'action':'deploy','definition':'unit/custom_card','position':{'row':0,'col':1}},at=0);s.advance(1)
    assert s.ctx.resources.current('system/battle','cards')==3
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_owned_payload_deployment_consumes_the_same_finite_stock():
    p=fixture();p['scenarioDraft']['resources']['cards']['initial']=1
    p['entities'].append({'id':'unit/owner','kind':'entity','components':{'spatial':{},'abilities':['ability/summon']}})
    p['abilities']=[{'id':'ability/summon','kind':'ability','activation':{'mode':'manual','on_start':[
        {'op':'spawn','definition':'unit/custom_card','owner':'source','parameters':{'position_from_payload':True}}]},'timeline':[]}]
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/owner','instanceAlias':'owner','position':{'row':0,'col':6}}]
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'owner','ability':'ability/summon','payload':{'position':{'row':0,'col':1}}},at=0)
    s.submit({'action':'skill','source':'owner','ability':'ability/summon','payload':{'position':{'row':0,'col':2}}},at=1);s.advance(2)
    assert s.ctx.resources.current('system/battle','cards')==0
    assert len(s.session.world.entities())==3
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_initial_buff_failure_after_public_payment_rolls_back_stock_dp_and_world():
    p=fixture();p['buffs']=[{'id':'buff/failure','kind':'buff','duration_seconds':1,'duration_rule':'rule/fail'}]
    p['rules']=[{'id':'rule/fail','kind':'rule','contract':'buff.duration','implementation':{'type':'expression','expression':'1 / 0'}}]
    p['entities'][0]['components']['buffs']={'initial':['buff/failure']}
    s=Engine.create(Compiler().compile(p));before=s.checkpoint()
    with pytest.raises(Exception):
        with s.session.atomic():s._execute_command({'action':'deploy','definition':'unit/custom_card','position':{'row':0,'col':1}})
    assert s.checkpoint()==before
