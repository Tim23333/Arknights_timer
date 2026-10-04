from copy import deepcopy
from ark_sim import Compiler,Engine
from tools.chapter08_buff_lifetime_review.test_joint_peer_v2 import package,INPUTS,CAPTURES,REGISTRY,command,removed,packets,capture
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim.tools.replay import replay
def active(inputs,params,context):
 return context['time']<3 if params['mode']=='marker' else context['time']<3 or context['time']>=5
def proof(p,tmp_path,end):
 INPUTS.append(deepcopy(p));reg={**REGISTRY,'peer.temporal_active':active};program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);command(s,'install',0);s.advance(3);pin=write_ordered(tmp_path/'applicability3.json',s.checkpoint());r=Engine.restore(program,load_bound(tmp_path/'applicability3.json',pin),providers=reg);s.advance(end-3);r.advance(end-3);h=replay(program,s.export_replay(),providers=reg);capture(s,'temporal_applicability');assert s.checkpoint()==r.checkpoint()==h.checkpoint();return s
def test_time_driven_marker_turns_inactive3_after_consuming_last_active_interval(tmp_path):
 p=package();p['buffs'][0]['duration_seconds']=8/30;p['buffs'][1]['active_rule']='rule/peer/applicability';p['rules'].append({'id':'rule/peer/applicability','kind':'rule','contract':'buff.applicability','parameters':{'mode':'marker'},'implementation':{'type':'provider','provider':'peer.temporal_active'}});p['entities'][0]['components']['buffs']={'initial':['buff/peer/fast']};s=proof(p,tmp_path,8);assert removed(s)==[5] and packets(s)==[2,4]
def test_time_driven_lifetime_owner_applicability_pauses3_to5_and_resumes_without_extra_consumption(tmp_path):
 p=package();p['buffs'][0]['active_rule']='rule/peer/applicability';p['buffs'][0]['lifetime']['count_when_inactive']=False;p['rules'].append({'id':'rule/peer/applicability','kind':'rule','contract':'buff.applicability','parameters':{'mode':'clock'},'implementation':{'type':'provider','provider':'peer.temporal_active'}});s=proof(p,tmp_path,11);assert removed(s)==[8] and packets(s)==[2,6]
