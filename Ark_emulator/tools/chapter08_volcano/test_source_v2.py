"""Six original cells,1000PURE,8..12 seeded clocks and exact CP/head."""
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.build_reference_stage_scenario_v2 import map_plan
from tools.chapter08_volcano.build_module_v1 import OUT,SOURCE,build,sha

def package():
    assert sha(OUT)=='bbd934d387e72ff5dfe9141c90b1185e3c8bf3baa310c4c0c562353f5825c857'
    p=json.loads(OUT.read_bytes());s=json.loads(SOURCE.read_bytes());mp=map_plan(s['stage_exact_map_data']['level_main_08-16']) if 'mapData' in s['stage_exact_map_data']['level_main_08-16'] else None
    if mp is None:
        native=json.loads((SOURCE.parent/'source.plan.v1.json').read_bytes())['stages']['level_main_08-16']['native_document'];mp=map_plan(native)
    cells=[{'row':i//mp['cols'],'col':i%mp['cols']} for i,t in enumerate(mp['tiles']) if t['tileKey']=='tile_volcano'];assert len(cells)==6
    p['entities']=[{'id':'unit/ch8/volcano/probe','kind':'entity','tags':['player'],'components':{'spatial':{},
        'attributes':{'base':{'max_hp':10000,'atk':0,'def':913,'mres':99}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
    infection_path=SOURCE.parents[2]/'chapter08_consumers/environment/infection.module.v3.json'
    infection=json.loads(infection_path.read_bytes())
    for group in ('rules','buffs','selectors','entities'):
        p.setdefault(group,[]).extend(infection.get(group,[]))
    p['scenarioDraft']={'id':'scene/ch8/volcano/source','ruleset':'ruleset/ark_standard','seed':81617,
        'map':{'rows':mp['rows'],'cols':mp['cols'],'tiles':mp['tiles'],'tile_mechanics':{**p['manifest']['metadata']['tile_profiles'],'tile_infection':infection['manifest']['metadata']['tile_profile'],'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}}},
        'initialEntities':[{'definition':'unit/ch8/volcano/probe','instanceAlias':'probe/'+str(i),'position':c} for i,c in enumerate(cells)]}
    return p,cells

def proof(p,tmp_path,split=200,end=400):
    from tools.chapter08_environment.policies_v1 import providers
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);s.advance(split);cp=tmp_path/'actual.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(end-split);r.advance(end-split);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events);return s

def test_source_rebuild_six_cells_every1000damage_and_sample_interval(tmp_path):
    assert json.loads(OUT.read_bytes())==build();p,cells=package();s=proof(p,tmp_path)
    fields=s.ctx.periodic_fields.state()['fields'];assert [f['cell'] for f in fields.values()]==cells
    triggers=[e for e in s.session.events if e['type']=='field.triggered'];hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(triggers)==len(hits)==6
    assert all(240<=e['time']<=360 for e in triggers)
    assert all(e['payload']['amount']==1000 and e['payload']['source'] is None for e in hits)
    assert all(s.ctx.resources.current('probe/'+str(i),'hp')==9000 for i in range(6))
    plans=[e for e in s.session.events if e['type']=='calculation' and e['payload']['calculation_id']=='field.trigger'];assert len(plans)==12
    for e in plans:
        t=e['payload']['trace'];u=t['inputs']['samples'][0]['value'];assert e['payload']['value']['next_delay_seconds']==8+4*u

@pytest.mark.parametrize('field,value',[('motion',2),('category',4),('target_free',True),('camouflage',True)])
def test_typed_unavailable_actor_keeps_trigger_without_damage(field,value,tmp_path):
    p,_=package();p['entities'][0]['components']['selection_state'][field]=value;s=proof(p,tmp_path)
    assert len([e for e in s.session.events if e['type']=='field.triggered'])==6
    assert not [e for e in s.session.events if e['type']=='damage.accepted']

def test_foreign_source_blackboard_values_rejected_not_silently_read():
    p,_=package();tile=next(t for t in p['scenarioDraft']['map']['tiles'] if t['tileKey']=='tile_volcano');tile['blackboard'][0]['value']=999
    with pytest.raises(ValueError,match='blackboard'):Compiler().compile(p)

def test_damage_afterhook_applied_toPURE_environmental_packet(tmp_path):
    p,_=package();p['rules'].append({'id':'rule/ch8/volcano/half','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'half','expression':"{'accepted':True,'amount':inputs.effect.settlement.amount*.5,'allocations':[],'events':[]}"}],'output':'nodes.half'}})
    p['buffs'] += [{'id':'buff/ch8/volcano/half','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/ch8/volcano/half'}]}];p['entities'][0]['components']['buffs']={'initial':['buff/ch8/volcano/half']};s=proof(p,tmp_path)
    assert all(e['payload']['amount']==500 for e in s.session.events if e['type']=='damage.accepted')
    assert all(s.ctx.resources.current('probe/'+str(i),'hp')==9500 for i in range(6))
