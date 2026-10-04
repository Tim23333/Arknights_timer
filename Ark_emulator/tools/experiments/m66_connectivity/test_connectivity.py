import hashlib,json
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]


def fixture(rows=2,cols=4):
    return {'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/barrier','kind':'entity','tags':['player'],
        'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'atk':0,'def':0,'block_count':0}},
         'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},
         'deployable':{'base_cost':2,'cooldown_seconds':0,'capacity':0,'terrain':'ground','parameters':{'max_instances':5},'stock':{'resource':'cards','amount':1},
           'rules':{'deploy.cost':'rule/fee'},'connectivity':{'rule':'rule/connected','parameters':{}}},
         'terrain_overlays':[{'key':'barrier','priority':0,'values':{'obstacleLikeMoveCost':True},'preserve':['passableMask'],'rule':'rule/terrain'}]}}],
      'rules':[{'id':'rule/connected','kind':'rule','contract':'deploy.connectivity','parameters':{'diagonal':False,'allow_corner_cut':False},'implementation':{'type':'provider','provider':'model.deploy.ground_connectivity'}},
               {'id':'rule/fee','kind':'rule','contract':'deploy.cost','implementation':{'type':'expression','expression':'inputs.base_cost'}},
               {'id':'rule/terrain','kind':'rule','contract':'terrain.tile_options','parameters':{'obstacle_like_cost':1000},'implementation':{'type':'provider','provider':'ark.terrain.tile_options'}}],
      'scenarioDraft':{'id':'scene/connectivity','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':rows,'cols':cols},'roster':['unit/barrier'],
        'resources':{'dp':{'initial':10,'capacity':10},'cards':{'initial':5,'capacity':5}},
        'parameters':{'deployment_routes':[{'id':'original','start':{'row':0,'col':0},'end':{'row':0,'col':cols-1}}]}}}


def make(p):
    raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'input':json.loads(raw)})
    return Engine.create(Compiler().compile(p),seed=64027)


def deploy(s,row,col,alias,at=0):
    s.submit({'action':'deploy','definition':'unit/barrier','alias':alias,'position':{'row':row,'col':col}},at=at)


def exact(s,tmp_path,end):
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.advance(end-s.session.time);r.advance(end-r.session.time)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_last_single_corridor_seal_rejects_public_without_payment_or_card(tmp_path):
    s=make(fixture(1));deploy(s,0,1,'barrier');s.advance(1)
    assert s.ctx.resources.current('system/battle','dp')==10 and s.ctx.resources.current('system/battle','cards')==5
    result=[e for e in s.session.events if e['type']=='command.rejected'];assert len(result)==1 and result[0]['payload']['reason']=='sealed_route:original'
    assert len(s.session.world.entities())==1 and s.ctx.state().get('terrain',{}).get('layers',{})=={}
    exact(s,tmp_path,3)


def test_detour_allowed_cost1000_preserved_then_last_seal_rejected_and_withdraw_reopens(tmp_path):
    s=make(fixture());deploy(s,0,1,'first');deploy(s,1,1,'seal',at=1)
    s.submit({'action':'withdraw','source':'first'},at=2);deploy(s,1,1,'second',at=3);s.advance(1)
    assert s.ctx.spatial.grid.passable(0,1) and s.ctx.spatial.grid.tile(0,1)['movementCost']==1000
    exact(s,tmp_path,5)
    assert s.ctx.resources.current('system/battle','cards')==3 and s.ctx.resources.current('system/battle','dp')==7
    assert s.ctx.alive('second') and not s.ctx.alive('first')
    assert [e['payload']['reason'] for e in s.session.events if e['type']=='command.rejected']==['sealed_route:original']


def test_future_original_route_checked_even_without_alive_or_scheduled_enemy(tmp_path):
    p=fixture();p['scenarioDraft']['parameters']['deployment_routes'].append({'id':'future','start':{'row':1,'col':0},'end':{'row':1,'col':3}})
    p['scenarioDraft']['parameters']['deployment_routes'][0]['end']={'row':0,'col':1}
    tiles=[{'buildableType':1,'passableMask':3} for _ in range(8)]
    for i in (2,3):tiles[i]={'buildableType':0,'passableMask':2}
    p['scenarioDraft']['map']['tiles']=tiles;s=make(p);deploy(s,1,2,'seal');s.advance(1)
    assert [e['payload']['reason'] for e in s.session.events if e['type']=='command.rejected']==['sealed_route:future']
    assert s.ctx.resources.current('system/battle','cards')==5;exact(s,tmp_path,3)


@pytest.mark.parametrize('patch',[lambda p:p['entities'][0]['components']['deployable'].update(connectivity={}),
    lambda p:p['scenarioDraft']['parameters'].pop('deployment_routes'),
    lambda p:p['scenarioDraft']['parameters'].update(deployment_routes=[]),
    lambda p:p['scenarioDraft']['parameters']['deployment_routes'].append(deepcopy(p['scenarioDraft']['parameters']['deployment_routes'][0])),
    lambda p:p['scenarioDraft']['parameters']['deployment_routes'][0]['start'].update(row=True),
    lambda p:p['scenarioDraft']['parameters']['deployment_routes'][0]['end'].update(col=99),
    lambda p:p['rules'][0].update(contract='deploy.cost'),
    lambda p:p['rules'][0]['parameters'].update(diagonal=1)])
def test_invalid_profile_route_or_rule_rejected_at_compile(patch):
    p=fixture();patch(p)
    with pytest.raises(ValueError):Compiler().compile(p)


def test_custom_connectivity_rule_can_replace_standard_decision(tmp_path):
    p=fixture(1);p['rules'][0]['implementation']={'type':'expression','expression':"{'accepted':True,'reason':'explicit allow alternate'}"}
    s=make(p);deploy(s,0,1,'accepted');s.advance(1);assert s.ctx.resources.current('system/battle','cards')==4;exact(s,tmp_path,3)


@pytest.mark.parametrize('expr',["{'accepted':1,'reason':'wrong type'}","{'accepted':True,'reason':'ok','extra':0}","{'accepted':1/0 > 0,'reason':'fault'}"])
def test_actual_custom_failure_rolls_back_every_atomic_partition(expr):
    p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':expr};s=make(p);before=s.checkpoint()
    with pytest.raises(Exception):
        with s.session.atomic():s._execute_command({'action':'deploy','definition':'unit/barrier','position':{'row':0,'col':1}})
    assert s.checkpoint()==before


@pytest.mark.parametrize('cut,accepted',[(False,False),(True,True)])
def test_declared_diagonal_corner_policy_changes_pure_result(cut,accepted):
    from ark_sim.domains.deploy_connectivity import ground_routes
    data={'grid':{'rows':2,'cols':2,'walkable':[True,False,False,True],'tiles':[{}]*4},
          'routes':[{'id':'corner','start':{'row':0,'col':0},'end':{'row':1,'col':1}}],
          'occupied':[],'proposed':{'row':0,'col':1},'parameters':{}}
    assert ground_routes(data,{'diagonal':True,'allow_corner_cut':cut},{})['accepted'] is accepted


def test_owned_spawn_uses_same_pre_payment_connectivity_and_rollback(tmp_path):
    p=fixture(1);p['entities'].append({'id':'unit/owner','kind':'entity','components':{'spatial':{},'abilities':['ability/spawn']}})
    p['abilities']=[{'id':'ability/spawn','kind':'ability','activation':{'mode':'manual','costs':[{'owner':'battle','resource':'dp','amount':2}],
        'on_start':[{'op':'spawn','target':'source','definition':'unit/barrier','owner':'source','parameters':{'deployment_payment_amount':2,'position_from_payload':True}}]},'timeline':[]}]
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/owner','instanceAlias':'owner','position':{'row':0,'col':0}}]
    s=make(p);s.submit({'action':'skill','source':'owner','ability':'ability/spawn','position':{'row':0,'col':1}},at=0);s.advance(1)
    if s.ctx.resources.current('system/battle','dp')!=10:
        from ark_sim.contracts import thaw
        directory=Path(__file__).resolve().parents[3]/'validation/campaign/m64_connectivity/owned_failure'
        directory.mkdir(exist_ok=True)
        (directory/'snapshot.json').write_text(json.dumps(thaw(s.snapshot()),ensure_ascii=False,indent=2),encoding='utf8')
        (directory/'input.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
    assert s.ctx.resources.current('system/battle','dp')==10 and s.ctx.resources.current('system/battle','cards')==5
    assert not [e for e in s.session.world.entities() if e['definition_id']=='unit/barrier'];exact(s,tmp_path,3)


def test_legal_partial_initial_override_uses_effective_deployable_merge(tmp_path):
    p=fixture();p['scenarioDraft']['initialEntities']=[{'definition':'unit/barrier','instanceAlias':'initial','position':{'row':0,'col':1},
        'components':{'deployable':{'connectivity':{'parameters':{'diagonal':True}}}}}]
    s=make(p);assert s.ctx.get('initial',('deployable','connectivity','parameters'))=={'diagonal':True}
    exact(s,tmp_path,3)


@pytest.mark.parametrize('where',['definition','initial'])
def test_explicit_null_profile_is_rejected_not_disabled(where):
    p=fixture()
    if where=='definition':p['entities'][0]['components']['deployable']['connectivity']=None
    else:p['scenarioDraft']['initialEntities']=[{'definition':'unit/barrier','position':{'row':0,'col':1},'components':{'deployable':{'connectivity':None}}}]
    with pytest.raises(ValueError,match='connectivity'):Compiler().compile(p)


def test_runtime_null_override_rejected_and_complete_checkpoint_unchanged():
    s=make(fixture());before=s.checkpoint()
    with pytest.raises(ValueError,match='connectivity'):
        s.ctx.lifecycle.create('unit/barrier',{'row':0,'col':1},component_overrides={'deployable':{'connectivity':None}})
    assert s.checkpoint()==before


def test_non_deployment_scripted_spawn_still_obeys_declared_placement_profile(tmp_path):
    p=fixture(1);p['entities'].append({'id':'unit/owner','kind':'entity','components':{'spatial':{},'abilities':['ability/plain_spawn']}})
    p['abilities']=[{'id':'ability/plain_spawn','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'spawn','target':'source','definition':'unit/barrier','position':{'row':0,'col':1}}]},'timeline':[]}]
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/owner','instanceAlias':'owner','position':{'row':0,'col':0}}]
    s=make(p);s.submit({'action':'skill','source':'owner','ability':'ability/plain_spawn'},at=0);s.advance(1)
    assert not [e for e in s.session.world.entities() if e['definition_id']=='unit/barrier']
    assert [e['payload']['reason'] for e in s.session.events if e['type']=='command.rejected']==['sealed_route:original'];exact(s,tmp_path,3)


def test_custom_phase_policy_can_allow_scripted_creation_without_relaxing_public_deploy(tmp_path):
    p=fixture(1);p['rules'][0]['implementation']={'type':'expression','expression':"{'accepted':ctx.placement_phase in ['create','created'],'reason':'explicit creation exception'}"}
    s=make(p);before=s.ctx.resources.current('system/battle','cards')
    actor=s.ctx.lifecycle.create('unit/barrier',{'row':0,'col':1});assert s.ctx.active(actor)
    assert s.ctx.resources.current('system/battle','cards')==before
    # API creation is explicitly outside public command replay; public gate
    # remains independent and rejects at prepare, rather than silently bypassing.
    cp=s.checkpoint()
    with pytest.raises(ValueError,match='creation exception'):
        with s.session.atomic():s._execute_command({'action':'deploy','definition':'unit/barrier','position':{'row':0,'col':2}})
    assert s.checkpoint()==cp


def activation_fixture(rows):
    p=fixture(rows);p['entities'].append({'id':'unit/controller','kind':'entity','components':{'spatial':{},'abilities':['ability/activate']}})
    p['abilities']=[{'id':'ability/activate','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'activate_predefined','target':'battle','parameters':{'key':'registered_barrier'}}]},'timeline':[]}]
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/controller','instanceAlias':'controller','position':{'row':0,'col':0}},
        {'definition':'unit/barrier','instanceAlias':'dormant','registration_key':'registered_barrier','position':{'row':0,'col':1},'active':False}]
    return p


def test_dormant_activation_sealing_route_rejected_by_public_action_and_saved_checkpoint(tmp_path):
    s=make(activation_fixture(1));assert not s.ctx.active('dormant')
    s.submit({'action':'skill','source':'controller','ability':'ability/activate'},at=1);s.advance(1);exact(s,tmp_path,4)
    assert not s.ctx.active('dormant') and s.ctx.get('dormant',('runtime','state'))=='dormant'
    assert [e['payload']['reason'] for e in s.session.events if e['type']=='command.rejected']==['sealed_route:original']
    assert not s.ctx.state().get('terrain',{}).get('layers',{}) and s.ctx.resources.current('system/battle','cards')==5


def test_dormant_activation_detour_allowed_with_no_implicit_card_payment(tmp_path):
    s=make(activation_fixture(2));s.submit({'action':'skill','source':'controller','ability':'ability/activate'},at=1);s.advance(1);exact(s,tmp_path,4)
    assert s.ctx.active('dormant') and s.ctx.spatial.grid.tile(0,1)['movementCost']==1000
    assert s.ctx.resources.current('system/battle','dp')==10 and s.ctx.resources.current('system/battle','cards')==5


def test_dormant_activation_direct_api_fault_rolls_back_registry_and_actor():
    s=make(activation_fixture(1));before=s.checkpoint()
    with pytest.raises(ValueError,match='sealed_route:original'):s.ctx.lifecycle.activate_predefined('registered_barrier')
    assert s.checkpoint()==before
