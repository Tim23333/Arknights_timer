from ark_sim import Compiler,Engine
from tools.campaign_run_diagnostics_v2 import summarize


def test_actual_movement_cursor_and_wait_deadline_are_readonly():
    p={'entities':[{'id':'unit/test_wait','kind':'entity','tags':['enemy','ground'],'components':{
        'spatial':{},'attributes':{'base':{'max_hp':10,'move_speed':1}},'resources':{'hp':{'initial':10,'capacity':10}}}}],
        'scenarioDraft':{'id':'scene/test/route_diag','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},'objectives':{},
            'initialEntities':[{'definition':'unit/test_wait','instanceAlias':'enemy','position':{'row':0,'col':0},
                'route':{'motionMode':'WALK','endPosition':{'row':0,'col':2},'checkpoints':[
                    {'type':'WAIT_FOR_SECONDS','time':2,'position':{'row':0,'col':0}}]}}]}}
    s=Engine.create(Compiler().compile(p),seed=4829);s.advance(1);before=s.checkpoint();r=summarize(s)
    enemy=r['alive_enemies'][0]
    assert enemy['route_cursor']==0 and enemy['route_state']['wait_until']==60
    assert enemy['next_checkpoint']['type']==1
    assert s.checkpoint()==before
