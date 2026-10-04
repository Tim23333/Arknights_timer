from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from tools.chapter08_buff_lifetime_review.test_joint_peer_v2 import package,INPUTS,CAPTURES,REGISTRY,command,removed,packets,capture
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim.tools.replay import replay
def temporal(inputs,params,context):
 when=context[params['unit']];return inputs['base']*(1 if when<params['threshold'] else 2)
@pytest.mark.parametrize('unit,threshold',[('time',3),('seconds',3/30)])
def test_temporal_clock_attribute_samples_end_of_actual_previous_tick_time_and_seconds(unit,threshold,tmp_path):
 p=package();p['rules'].append({'id':'rule/peer/time_attribute','kind':'rule','contract':'attributes.effective','parameters':{'unit':unit,'threshold':threshold},'implementation':{'type':'provider','provider':'peer.temporal_attribute'}});p['entities'][0]['components']['attributes']['attribute_rules']={'clock_rate':{'attributes.effective':'rule/peer/time_attribute'}};INPUTS.append(deepcopy(p));reg={**REGISTRY,'peer.temporal_attribute':{'callable':temporal,'version':'1'}};program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=818300);command(s,'install',0);s.advance(2);pin=write_ordered(tmp_path/'temporal2.json',s.checkpoint());r=Engine.restore(program,load_bound(tmp_path/'temporal2.json',pin),providers=reg);s.advance(6);r.advance(6);h=replay(program,s.export_replay(),providers=reg);capture(s,'attribute_'+unit);assert s.checkpoint()==r.checkpoint()==h.checkpoint() and removed(s)==[5] and packets(s)==[2,4]
