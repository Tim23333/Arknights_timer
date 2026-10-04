"""Independent fixtures, executed only after the area candidate is frozen."""
import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m46_area_members_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def fixture():
    actor=lambda name,tags,hp,atk:{'id':'unit/'+name,'kind':'entity','tags':tags,'components':{'spatial':{},'attributes':{'base':{'max_hp':hp,'atk':atk,'def':0,'mres':0}},'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    src=actor('caster',['caster'],400,37);src['components']['abilities']=['ability/area']
    effect={'op':'area','center':'target','membership_rule':'rule/area','parameters':{'offsets':[[a,b] for a in (-1,0,1) for b in (-1,0,1)]},'filters':[{'tag':'victim'}],'effects':[{'op':'damage','damage_type':'true'}]}
    return {'manifest':{'requires':['preset/ark_standard']},'entities':[src,actor('victim',['victim'],1000,0)],
        'rules':[{'id':'rule/area','kind':'rule','contract':'area.members','implementation':{'type':'provider','provider':'ark.area.cell_offsets'}}],
        'selectors':[{'id':'selector/main','kind':'selector','region':{'type':'all'},'filters':[{'tag':'primary'}],'limit':1}],
        'abilities':[{'id':'ability/area','kind':'ability','selector':'selector/main','activation':{'mode':'manual','on_start':[effect]},'timeline':[]}],
        'scenarioDraft':{'id':'scene/area/peer','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':7,'cols':7},'initialEntities':[
            {'definition':'unit/caster','instanceAlias':'src','position':{'row':0,'col':0}},
            *[{'definition':'unit/victim','instanceAlias':name,'tags':['victim','primary'] if name=='main' else ['victim'], 'position':{'row':r,'col':c},
               'components':{'spatial':{'motion_mode':1}} if name=='flycorner' else {}} for name,r,c in [('main',3,3),('flycorner',4.49,4.49),('outside',4.5,4.5),('othercorner',1.5,1.5)]]]}}
def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=4619)

def test_grid_splash_is_separate_from_primary_target_and_continuous_radius():
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=4619);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=0);s.advance(1)
    assert [s.ctx.resources.current(x,'hp') for x in ('main','flycorner','outside','othercorner')]==[963,963,1000,963]
    assert len([e for e in s.session.events if e['type']=='damage.accepted'])==3 and s.snapshot()==replay(program,s.export_replay()).snapshot()

def test_opt_in_rule_has_source_target_scope_and_actual_calculation_trace():
    p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':'[ctx.target.id] if ctx.source.components.resources.hp.current == 400 else []'}
    s=make(p);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=0);s.advance(1)
    assert s.ctx.resources.current('main','hp')==963 and s.ctx.resources.current('flycorner','hp')==1000
    events=[e for e in s.session.events if e['type']=='calculation' and e['payload']['calculation_id']=='area.members'];assert len(events)==1
    assert events[0]['payload']['rule_id']=='rule/area' and events[0]['payload']['source']==s.session.world.resolve('src')

def test_explicit_ability_effect_owner_context_is_available_to_replacement_rule():
    p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':"[ctx.target.id] if ctx.ability.id == 'ability/area' and ctx.effect.parameters.offsets[0][0] == -1 and ctx.owner.id == ctx.source.id else []"}
    s=make(p);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=0);s.advance(1)
    assert s.ctx.resources.current('main','hp')==963 and s.ctx.resources.current('flycorner','hp')==1000

def test_custom_membership_rule_replaces_grid_math_and_preserves_selected_order():
    p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':'[inputs.candidates[2].id, inputs.candidates[0].id]'}
    s=make(p);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=0);s.advance(1)
    packets=[e for e in s.session.events if e['type']=='damage.accepted']
    assert [e['payload']['target'] for e in packets]==[s.session.world.resolve('outside'),s.session.world.resolve('main')]
    assert s.ctx.resources.current('outside','hp')==963 and s.ctx.resources.current('flycorner','hp')==1000

@pytest.mark.parametrize('expression',['[inputs.candidates[0].id,inputs.candidates[0].id]','[True]','["main"]','[999999]','[1]'])
def test_output_must_be_unique_int_ids_from_actual_filtered_candidates(expression):
    p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':expression};s=make(p);before=s.checkpoint()
    with pytest.raises(Exception):s.ctx.effects.execute('src',['main'],p['abilities'][0]['activation']['on_start'][0])
    assert s.checkpoint()==before

def test_membership_on_nonarea_effect_is_compile_rejected():
    p=fixture();p['abilities'][0]['activation']['on_start'][0]={'op':'damage','damage_type':'true','membership_rule':'rule/area'}
    with pytest.raises(ValueError):Compiler().compile(p)

def test_wrong_calculation_contract_is_compile_rejected():
    p=fixture();p['rules'][0]['contract']='targeting.selection'
    with pytest.raises(ValueError):Compiler().compile(p)

def test_two_duplicate_offsets_do_not_apply_two_packets():
    p=fixture();p['abilities'][0]['activation']['on_start'][0]['parameters']['offsets']=[[0,0],[0,0]]
    s=make(p);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=0);s.advance(1)
    assert s.ctx.resources.current('main','hp')==963 and len([e for e in s.session.events if e['type']=='damage.accepted'])==1

def test_public_area_command_ordered_disk_checkpoint_and_replay(tmp_path):
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=4620);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=3);s.advance(2)
    path=tmp_path/'area.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(4);r.advance(4)
    assert s.ctx.resources.current('flycorner','hp')==963 and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()

def test_map_edge_negative_half_margin_has_no_clamped_duplicate_cells():
    p=fixture();p['scenarioDraft']['initialEntities'][1]['position']={'row':0,'col':0}
    p['scenarioDraft']['initialEntities'][2]['position']={'row':-.5,'col':-.5}
    p['scenarioDraft']['initialEntities'][3]['position']={'row':1.5,'col':0}
    p['scenarioDraft']['initialEntities'][4]['position']={'row':.49,'col':1.49}
    s=make(p);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=0);s.advance(1)
    assert [s.ctx.resources.current(x,'hp') for x in ('main','flycorner','outside','othercorner')]==[963,963,1000,963]
    assert len([e for e in s.session.events if e['type']=='damage.accepted'])==3

def test_late_member_failure_restores_earlier_damage_trace_events_and_rng():
    p=fixture();bad=deepcopy(p['entities'][1]);bad['id']='unit/bad';bad['rules']={'damage.pipeline':'rule/fail'};p['entities'].append(bad)
    p['scenarioDraft']['initialEntities'][-1]['definition']='unit/bad';p['scenarioDraft']['initialEntities'][-1]['tags']=['victim','bad']
    p['rules'].append({'id':'rule/fail','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'error','expression':'1 / 0'}],'output':'nodes.error'}})
    area=p['abilities'][0]['activation']['on_start'][0];area['effects'].insert(0,{'op':'random','stream':'imp','probability':1,'on_success':[{'op':'modify_resource','resource':'hp','delta':-1}]})
    area['effects'][-1]['on_success']=[{'op':'damage','damage_type':'true','condition':"'bad' in inputs.targets[0].tags",'rules':{'damage.pipeline':'rule/fail'}}]
    s=make(p);before=s.checkpoint()
    with pytest.raises(Exception):s.ctx.effects.execute('src',['main'],area)
    assert s.checkpoint()==before

def test_late_scheduled_area_can_use_retired_source_without_fabricating_new_source():
    p=fixture();area=deepcopy(p['abilities'][0]['activation']['on_start'][0]);area['center_position']={'row':3,'col':3}
    p['abilities'][0]['activation']['on_start']=[{'op':'schedule','delay_seconds':.1,'effect':area}]
    director=deepcopy(p['entities'][0]);director['id']='unit/director';director['tags']=['director'];director['components']['abilities']=['ability/retire'];p['entities'].append(director)
    p['selectors'].append({'id':'selector/source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'caster'}]})
    p['abilities'].append({'id':'ability/retire','kind':'ability','selector':'selector/source','activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdraw'}}]},'timeline':[]})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':1}})
    program=Compiler().compile(p);s=Engine.create(program,seed=4621);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=0);s.submit({'action':'skill','source':'director','ability':'ability/retire'},at=1);s.advance(5)
    assert not s.ctx.alive('src') and s.ctx.resources.current('flycorner','hp')==963
    packets=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(packets)==3 and all(e['payload']['source']==s.session.world.resolve('src') for e in packets)
    assert s.snapshot()==replay(program,s.export_replay()).snapshot()

def test_old_radius_path_has_no_new_membership_calculation():
    p=fixture();area=p['abilities'][0]['activation']['on_start'][0];area.pop('membership_rule');area.pop('parameters');area['radius']=1.5
    s=make(p);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=0);s.advance(1)
    assert [s.ctx.resources.current(x,'hp') for x in ('main','flycorner','outside','othercorner')]==[963,1000,1000,1000]
    assert not any(e['type']=='calculation' and e['payload']['calculation_id']=='area.members' for e in s.session.events)

def test_member_death_is_counted_once_and_does_not_duplicate_other_packets():
    p=fixture();p['scenarioDraft']['initialEntities'][1]['components']={'resources':{'hp':{'initial':20,'capacity':1000,'role':'health'}}}
    p['scenarioDraft']['initialEntities'][1]['tags']=['victim','primary','enemy']
    s=make(p);s.submit({'action':'skill','source':'src','ability':'ability/area'},at=0);s.advance(1)
    assert not s.ctx.alive('main') and s.ctx.state()['kills']==1 and s.ctx.state()['leaks']==0
    assert s.ctx.resources.current('flycorner','hp')==963 and len([e for e in s.session.events if e['type']=='damage.accepted'])==3
