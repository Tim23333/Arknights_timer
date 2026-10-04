"""A finite current-wave request retains all actors and pending births."""
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

EFFECT={'op':'finish_timeline_wave','target':'source','parameters':{
    'finish_and_skip':False,'track_source_at_next_wave':False,
    'track_source_wave_delta':0,'track_all_managed_at_next_wave':False}}


def package():
    unit={'id':'unit/wave/source','kind':'entity','components':{
        'attributes':{'base':{'max_hp':100,'atk':1}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},
        'spatial':{},'abilities':['ability/wave/release'],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    spawn=lambda alias:{'kind':'spawn','managed':True,'blocks_wave':True,'spawn':{
        'definition':unit['id'],'instanceAlias':alias,'position':{'row':0,'col':0}}}
    first=spawn('source');late=spawn('late');late['delay_seconds']=10/30
    second=spawn('next')
    return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},
        'entities':[unit], 'abilities':[{'id':'ability/wave/release','kind':'ability',
            'activation':{'mode':'manual'},'timeline':[{'at':0,'effect':EFFECT}]}],
        'scenarioDraft':{'id':'scene/wave/request','ruleset':'ruleset/ark_standard',
            'map':{'rows':1,'cols':1},'objectives':{},'timeline':{
                'policy':'managed_clear','negative_timeout_policy':'wait_for_clear',
                'waves':[{'post_delay_seconds':3/30,'fragments':[{'actions':[first,late]}]},
                         {'pre_delay_seconds':2/30,'fragments':[{'actions':[second]}]}]}}}


def test_pending_births_actors_and_delays_preserved_cp_head(tmp_path):
    s=Engine.create(Compiler().compile(package()),seed=7188)
    s.submit({'action':'skill','source':'source','ability':'ability/wave/release'},at=2)
    s.advance(3);cp=tmp_path/'request3.json';pin=write_ordered(cp,s.checkpoint())
    r=Engine.restore(s.program,load_bound(cp,pin));s.advance(14);r.advance(14)
    assert s.checkpoint()==r.checkpoint()==replay(s.program,s.export_replay()).checkpoint()
    assert all(s.ctx.alive(n) for n in ('source','late','next'))
    assert s.ctx.state()['kills']==s.ctx.state()['leaks']==0
    born=[(e['time'],e['payload']['target']) for e in s.session.events if e['type']=='entity.created']
    assert [t for t,_ in born]==[0,10,15]
    assert sum(e['type']=='timeline.wave_completed' for e in s.session.events)==1
    assert s.ctx.state()['timeline']['members'][str(s.session.world.resolve('source'))]['wave']==0
    assert s.ctx.state()['timeline']['wave_index']==1


def test_same_wave_repeat_request_is_idempotent_not_wave_skip():
    s=Engine.create(Compiler().compile(package()))
    for tick in (2,3):s.submit({'action':'skill','source':'source','ability':'ability/wave/release'},at=tick)
    s.advance(5)
    assert sum(e['type']=='timeline.finish_requested' for e in s.session.events)==1
    assert s.ctx.state()['pending_waves']==2


@pytest.mark.parametrize('key,value',[('finish_and_skip',True),('track_source_wave_delta',False),('track_source_at_next_wave',1)])
def test_unimplemented_flag_and_boolean_integer_rejected(key,value):
    p=package();p['abilities'][0]['timeline'][0]['effect']=deepcopy(EFFECT)
    p['abilities'][0]['timeline'][0]['effect']['parameters'][key]=value
    with pytest.raises(ValueError):Compiler().compile(p)
