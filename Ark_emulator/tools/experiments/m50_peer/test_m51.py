import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m51_deploy_payment_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.domains.deployment import prepare,record
from ark_sim.tools.replay import replay
def fixture():
    return {'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/widget','kind':'entity','tags':['player'],'components':{'spatial':{},
        'attributes':{'base':{'max_hp':90}},'resources':{'hp':{'initial':90,'capacity':90,'role':'health'}},
        'deployable':{'base_cost':4,'capacity':0,'cooldown_seconds':0,'terrain':'ground','parameters':{'max_instances':20},'stock':{'resource':'tickets','amount':1}}}}],
        'scenarioDraft':{'id':'scene/stock/peer','ruleset':'ruleset/ark_standard','objectives':{},'roster':['unit/widget'],'map':{'rows':1,'cols':8},
            'resources':{'dp':{'initial':50,'capacity':50},'tickets':{'initial':3,'capacity':3}}}}
def make(p=None):
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    providers={**BUILTIN_PROVIDERS,'peer.floor':floor_bounds}
    return Engine.create(Compiler(providers=providers).compile(p or fixture()),seed=5019,providers=providers)

def floor_bounds(inputs,params,context):
    value=max(inputs['candidate'],params['floor']);return {'accepted':True,'value':value,'overflow':inputs['candidate']-value}
floor_bounds.version='independent_m50_floor_v1'
def command(i):return {'action':'deploy','definition':'unit/widget','alias':'widget'+str(i),'position':{'row':0,'col':i}}

def test_three_stock_is_exhausted_exactly_public_not_replenished_on_withdraw():
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=5019)
    for i in range(4):s.submit(command(i),at=i)
    s.submit({'action':'withdraw','source':'widget0'},at=4);s.advance(5)
    assert s.ctx.resources.current('system/battle','tickets')==0
    assert len([e for e in s.session.events if e['type']=='command.rejected'])==1 and s.snapshot()==replay(program,s.export_replay()).snapshot()

def test_same_resource_deployment_and_stock_total_exactly_charged():
    p=fixture();p['entities'][0]['components']['deployable']['stock']['resource']='dp';p['scenarioDraft']['resources']['dp']['initial']=5
    s=make(p);s.submit(command(0),at=0);s.advance(1);assert s.ctx.resources.current('system/battle','dp')==0
    assert s.ctx.get('widget0',('deployable','paid_cost'))==4

def test_partial_stock_payment_via_actual_bounds_rule_rejects_and_rolls_back_whole_command():
    p=fixture();p['rules']=[{'id':'rule/keepone','kind':'rule','contract':'resource.bounds','parameters':{'floor':1},'implementation':{'type':'provider','provider':'peer.floor'}}]
    p['scenarioDraft']['resources']['tickets'].update(initial=1,bounds_rule='rule/keepone')
    s=make(p);before=s.checkpoint()
    with pytest.raises(ValueError,match='must be exact'):
        with s.session.atomic():s._execute_command(command(0))
    assert s.checkpoint()==before

def test_second_record_same_actor_cannot_charge_stock_again():
    s=make();plan=prepare(s.ctx,'unit/widget',{'row':0,'col':0});s.submit(command(0),at=0);s.advance(1);after_prepare=s.checkpoint()
    with pytest.raises(ValueError):
        with s.session.atomic():record(s.ctx,'widget0',plan)
    assert s.checkpoint()==after_prepare

def test_separate_stock_does_not_allow_partial_DP_payment_to_be_recorded_as_full():
    p=fixture();p['rules']=[{'id':'rule/dp_floor','kind':'rule','contract':'resource.bounds','parameters':{'floor':3},'implementation':{'type':'provider','provider':'peer.floor'}}]
    p['scenarioDraft']['resources']['dp'].update(initial=4,bounds_rule='rule/dp_floor')
    s=make(p);s.submit(command(0),at=0);s.advance(1)
    assert [e['type'] for e in s.session.events if e['type'].startswith('command.')]==['command.rejected']
    assert s.ctx.resources.current('system/battle','dp')==4 and s.ctx.resources.current('system/battle','tickets')==3

def test_record_without_external_atomic_restores_marker_and_resource_on_bounds_failure():
    p=fixture();p['rules']=[{'id':'rule/ticket_floor','kind':'rule','contract':'resource.bounds','parameters':{'floor':1},'implementation':{'type':'provider','provider':'peer.floor'}}]
    p['scenarioDraft']['resources']['tickets'].update(initial=1,bounds_rule='rule/ticket_floor');s=make(p)
    plan=prepare(s.ctx,'unit/widget',{'row':0,'col':0});ref=s.ctx.lifecycle.create('unit/widget',{'row':0,'col':0},alias='unrecorded',deployed=True);before=s.checkpoint()
    with pytest.raises(ValueError,match='must be exact'):record(s.ctx,ref,plan)
    assert s.checkpoint()==before and not s.ctx.get(ref,('runtime','deployment_recorded'),False)

def test_outer_failure_after_successful_record_restores_marker_stock_DP_and_actor():
    s=make();before=s.checkpoint()
    with pytest.raises(RuntimeError):
        with s.session.atomic():
            s._execute_command(command(0));assert s.ctx.get('widget0',('runtime','deployment_recorded')) is True
            raise RuntimeError('independent outer failure after actual recorded payment')
    assert s.checkpoint()==before
    s.submit(command(0),at=0);s.advance(1);assert s.ctx.resources.current('system/battle','tickets')==2 and s.ctx.get('widget0',('runtime','deployment_recorded')) is True

def test_no_stock_partial_DP_is_rejected_but_normal_no_stock_is_exact():
    p=fixture();p['entities'][0]['components']['deployable'].pop('stock');p['rules']=[{'id':'rule/dp_floor','kind':'rule','contract':'resource.bounds','parameters':{'floor':3},'implementation':{'type':'provider','provider':'peer.floor'}}]
    p['scenarioDraft']['resources']['dp'].update(initial=4,bounds_rule='rule/dp_floor');s=make(p);s.submit(command(0),at=0);s.advance(1)
    assert len(s.session.world.entities())==1 and s.ctx.resources.current('system/battle','dp')==4
    p['scenarioDraft']['resources']['dp'].pop('bounds_rule');s=make(p);s.submit(command(0),at=0);s.advance(1)
    assert s.ctx.resources.current('system/battle','dp')==0 and s.ctx.get('widget0',('deployable','paid_cost'))==4 and s.ctx.get('widget0',('runtime','deployment_recorded')) is True

def test_owned_actual_cast_payment_ledger_and_stock_record_is_shared():
    p=fixture();p['entities'].append({'id':'unit/host','kind':'entity','components':{'spatial':{},'abilities':['ability/child']}})
    p['abilities']=[{'id':'ability/child','kind':'ability','activation':{'mode':'manual','costs':[{'owner':'battle','resource':'dp','amount':4}],
        'on_start':[{'op':'spawn','definition':'unit/widget','owner':'source','parameters':{'position_from_payload':True,'deployment_payment_amount':4}}]},'timeline':[]}]
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/host','instanceAlias':'host','position':{'row':0,'col':7}}];s=make(p)
    s.submit({'action':'skill','source':'host','ability':'ability/child','payload':{'position':{'row':0,'col':0}}},at=0);s.advance(1)
    child=next(e['id'] for e in s.session.world.entities() if e['definition_id']=='unit/widget')
    assert s.ctx.resources.current('system/battle','dp')==46 and s.ctx.resources.current('system/battle','tickets')==2
    assert s.ctx.get(child,('deployable','paid_cost'))==4 and s.ctx.get(child,('runtime','deployment_recorded')) is True
    assert s.ctx.get(child,('ownership','owner'))==s.session.world.resolve('host')

@pytest.mark.parametrize('patch',[{'resource':'missing'},{'rule':'rule/wrong'},{'amount':True}])
def test_missing_resource_and_wrong_cost_contract_strict_before_runtime(patch):
    p=fixture();p['entities'][0]['components']['deployable']['stock'].update(patch)
    if patch.get('rule'):p['rules']=[{'id':'rule/wrong','kind':'rule','contract':'movement.distance','implementation':{'type':'expression','expression':'1'}}]
    with pytest.raises(ValueError):Compiler().compile(p)
