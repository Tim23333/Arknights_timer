"""Generic authored fields consume explicit map profiles and real Buff domains."""
from pathlib import Path
import sys
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m38_integrated_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def fixture():
    p={'manifest':{'requires':['preset/ark_standard']},'entities':[
        {'id':'unit/field','kind':'entity','tags':['tile_field_owner'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1,'atk':0}},
             'resources':{'hp':{'initial':1,'capacity':1}},'buffs':{'initial':['buff/field_parent']}}},
        {'id':'unit/target','kind':'entity','tags':['player','ground'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1000,'atk':0,'ratio':0}},
             'resources':{'hp':{'initial':500,'capacity':1000,'role':'health','recovery_rule':'rule/ratio','recovery':{'mode':'continuous'}}},'abilities':['ability/in','ability/out']}}],
       'buffs':[{'id':'buff/field_parent','kind':'buff','aura':{'selector':'selector/cell','buff':'buff/member'}},
                {'id':'buff/member','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'ratio','layer':'flat','value':.03}]}],
       'selectors':[{'id':'selector/cell','kind':'selector','region':{'type':'grid_offsets','offsets':[[0,0]],'rotate_with_facing':False},'filters':[{'tag':'player'},{'state':'alive'}]}],
       'rules':[{'id':'rule/ratio','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current + inputs.delta_seconds * inputs.attributes.max_hp * inputs.attributes.ratio'}}],
       'abilities':[{'id':'ability/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':col}}]},'timeline':[]} for name,col in [('in',1),('out',2)]],
       'scenarioDraft':{'id':'scene/custom_field','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3,'tiles':[
            {'tileKey':'tile_floor','buildableType':1,'passableMask':1},
            {'tileKey':'custom_rest_cell','buildableType':1,'passableMask':1,'blackboard':[{'key':'ratio','value':.03,'valueStr':None}]},
            {'tileKey':'tile_floor','buildableType':1,'passableMask':1}],
            'tile_mechanics':{'custom_rest_cell':{'type':'occupancy_buff_field','definition':'unit/field','expected_blackboard':{'ratio':.03}}}},
          'initialEntities':[{'definition':'unit/target','instanceAlias':'target','position':{'row':0,'col':0}}]}}
    return p


def test_arbitrary_map_field_real_entry_leave_and_durable_replay(tmp_path):
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=3101)
    assert 'unit/field' in program.definitions
    fields=s.ctx.state()['tile_fields'];assert list(fields)==['0:1']
    owner=fields['0:1']['owner'];assert s.ctx.entity(owner)['tags']==('tile_field_owner',) or list(s.ctx.entity(owner)['tags'])==['tile_field_owner']
    s.submit({'action':'skill','source':'target','ability':'ability/in'},at=3)
    s.submit({'action':'skill','source':'target','ability':'ability/out'},at=33);s.advance(20)
    path=tmp_path/'cp.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(15);r.advance(15)
    assert s.ctx.resources.current('target','hp')==pytest.approx(530)
    assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
    assert s.ctx.get(owner,('buffs','instances'))[0]['aura_members']=={}


@pytest.mark.parametrize('mutation',[lambda p:p['scenarioDraft']['map']['tiles'][1]['blackboard'].append({'key':'unknown','value':1}),
    lambda p:p['scenarioDraft']['map']['tiles'][1]['blackboard'][0].update(value=.04),
    lambda p:p['scenarioDraft']['map']['tiles'][1].update(effects=['unconsumed']),
    lambda p:p['scenarioDraft']['map']['tile_mechanics']['custom_rest_cell'].update(definition='ability/in'),
    lambda p:p['entities'][0]['tags'].append('enemy')])
def test_unknown_operands_or_wrong_field_owner_reject_before_runtime(mutation):
    p=fixture();mutation(p)
    with pytest.raises(ValueError):Compiler().compile(p)


def test_each_cell_has_independent_parent_and_shared_content_definition():
    p=fixture();p['scenarioDraft']['map']['tiles'][2]=deepcopy(p['scenarioDraft']['map']['tiles'][1])
    s=Engine.create(Compiler().compile(p),seed=3102);fields=s.ctx.state()['tile_fields']
    assert len(fields)==2 and fields['0:1']['owner']!=fields['0:2']['owner']
    assert s.ctx.entity(fields['0:1']['owner'])['definition_id']==s.ctx.entity(fields['0:2']['owner'])['definition_id']=='unit/field'


def test_blackboard_reference_like_keys_are_data_not_implicit_dependencies():
    p=fixture();profile=p['scenarioDraft']['map']['tile_mechanics']['custom_rest_cell'];profile['expected_blackboard']={'rule':.03}
    p['scenarioDraft']['map']['tiles'][1]['blackboard'][0]['key']='rule'
    s=Engine.create(Compiler().compile(p));assert s.ctx.state()['tile_fields']['0:1']['source_blackboard']=={'rule':.03}


def test_field_profile_without_explicit_tiles_is_rejected():
    p=fixture();p['scenarioDraft']['map'].pop('tiles')
    with pytest.raises(ValueError,match='explicit row-major'):Compiler().compile(p)


def test_virtual_field_owner_never_enters_combat_target_or_area_population():
    p=fixture();p['selectors'].append({'id':'selector/all','kind':'selector','region':{'type':'all'}})
    p['entities'][1]['dependencies']=['selector/all']
    s=Engine.create(Compiler().compile(p));owner=s.ctx.state()['tile_fields']['0:1']['owner']
    assert not s.ctx.selectable(owner) and not s.ctx.effect_target_available(owner)
    assert s.ctx.spatial.select('target','selector/all')==[s.session.world.resolve('target')]
    assert s.ctx.spatial.eligible('target','selector/all')==[s.session.world.resolve('target')]
    assert s.ctx.active(owner)
