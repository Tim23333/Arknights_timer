import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter07_boss.policies_v2 import providers
from tools.experiments.wave_finish_peer.test_wave_bound import package,make,finish,capture,ev,wave,spawn,INPUTS,CAPTURES
ROOT=Path(__file__).resolve().parents[3]
def test_real_hpzero_rebirth_onbegin_releases_enemy_gate_not_future_birth(tmp_path):
 p=package();p['rules']=[{'id':'rule/w/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity*inputs.parameters.ratio'}}];p['entities'][0]['components']['rebirth']={'resource':'hp','max_count':1,'delay_seconds':100/30,'restore_ratio':1,'restore_rule':'rule/w/restore','on_begin':[finish()]}
 p['abilities'].append({'id':'ability/w/kill','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':3,'resource':'hp','value':0}]},'timeline':[]});p['entities'].append({'id':'unit/w/controller','kind':'entity','components':{'abilities':['ability/w/kill'],'spatial':{}}});p['scenarioDraft']['initialEntities']=[{'definition':'unit/w/controller','instanceAlias':'director','position':{'row':0,'col':1}}]
 s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/w/kill'},at=1);s.advance(2);assert s.ctx.alive('first') and not s.ctx.active('first') and s.ctx.resources.current('first','hp')==0 and len(ev(s,'timeline.finish_requested'))==1
 pin=write_ordered(tmp_path/'zero2.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'zero2.json',pin));s.advance(12);r.advance(12);h=replay(s.program,s.export_replay());capture(s,'actual_rebirth_wave');assert s.checkpoint()==r.checkpoint()==h.checkpoint() and s.ctx.state()['timeline']['wave_index']==1 and s.ctx.resources.current('first','hp')==0
def test_unchanged_actual_boss_in_managed_wave_source_cp6_head(tmp_path):
 values=json.loads((ROOT/'validation/campaign/chapter07_joint_independent_complete/inputs.json').read_text());p=next(x for x in values if x['scenarioDraft']['id']=='scene/j/actual_source');boss=p['entities'][0]['id'];p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][1:];p['abilities'][-1]['activation']['on_start'][0]['target']=4
 p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':0,'post_delay_seconds':0,'max_wait_seconds':-1,'fragments':[{'pre_delay_seconds':0,'actions':[{'kind':'spawn','managed':True,'blocks_wave':True,'blocks_fragment':False,'spawn':{'definition':boss,'instanceAlias':'boss','position':{'row':0,'col':0}}}]}]}]}
 INPUTS.append(p);reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),seed=7074,providers=reg);s.submit({'action':'skill','source':'director','ability':'ability/j/sourcekill'},at=5);s.advance(6);assert s.ctx.resources.current('boss','hp')==0 and s.ctx.alive('boss') and not s.ctx.active('boss')
 pin=write_ordered(tmp_path/'boss_wave6.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'boss_wave6.json',pin),providers=reg);s.advance(30);r.advance(30);h=replay(s.program,s.export_replay(),providers=reg);capture(s,'actual_source_managed_wave');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 assert s.ctx.state()['timeline']['wave_index']==0 and s.ctx.state()['timeline']['phase']=='wave_gate'
 hits=[e for e in ev(s,'damage.accepted') if e['payload'].get('ability','').endswith('/immo_action')];assert len(hits)==1 and abs(hits[0]['payload']['amount']-116.704)<1e-8
