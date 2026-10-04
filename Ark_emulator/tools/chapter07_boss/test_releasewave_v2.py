"""Phase0 literal on_remove releases real wave without killing or skipping births."""
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter07_boss.test_combined_source_v2 import package as original,deploy,kill,ev
from tools.chapter07_boss.build_mechanism_v1 import OUT,UID
from tools.chapter07_boss.policies_v2 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def package(release=True):
 q=original();p=json.loads((OUT/('releasewave.mechanism.v1.json' if release else 'combined.mechanism.v2.json')).read_bytes());p['entities']+=q['entities'][1:]
 for k in ['abilities','selectors']:p[k]+=[d for d in q[k] if d['id'].startswith(('ability/test/','selector/test/'))]
 p['scenarioDraft']=q['scenarioDraft'];p['scenarioDraft']['initialEntities']=[x for x in p['scenarioDraft']['initialEntities'] if x['instanceAlias'] not in ['boss','ally']]
 dummy='unit/test/patrt/wave_member';p['entities'].append({'id':dummy,'kind':'entity','tags':['wave_probe'],'components':{'attributes':{'base':{'max_hp':1000,'atk':0}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
 def spawn(definition,alias,delay,blocks=False):return {'kind':'spawn','spawn':{'definition':definition,'instanceAlias':alias,'position':{'row':2,'col':2} if alias=='boss' else {'row':4,'col':6}},'delay_seconds':delay,'managed':True,'blocks_wave':blocks,'blocks_fragment':False,'count':1,'interval_seconds':0}
 p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':0,'post_delay_seconds':1,'max_wait_seconds':-1,'fragments':[{'pre_delay_seconds':0,'actions':[spawn(UID,'boss',1,True),spawn(dummy,'ally0',0,False),spawn(dummy,'future0',10,False)]}]},{'pre_delay_seconds':2,'post_delay_seconds':0,'max_wait_seconds':-1,'fragments':[{'pre_delay_seconds':0,'actions':[spawn(dummy,'next1',0,False)]}]}]}
 return p
def make(release=True):return Engine.create(Compiler(providers=providers()).compile(package(release)),providers=providers(),seed=7187)
def setup(release=True):s=make(release);deploy(s);kill(s,35);return s
def test_actual_original_without_onfinish_keeps_hp0_alive_boss_blocking_wave():
 s=setup(False);s.session.advance(430);assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss')
 assert s.session.world.resolve('future0') and not [e for e in ev(s,'timeline.action') if e['payload']['wave']==1]
 state=s.ctx.state()['timeline'];assert state['wave_index']==0 and state['phase']=='wave_gate' and str(s.session.world.resolve('boss')) in state['members']
def test_actual_source_buff_onfinish_request_preserves_futurebirth_then_postpre_delays():
 s=setup();s.session.advance(430);assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss') and not ev(s,'entity.died')
 assert s.session.world.resolve('future0') and s.session.world.resolve('next1')
 starts=[e for e in ev(s,'timeline.action') if e['payload']['kind']=='spawn'];assert any(e['time']==300 and e['payload']['wave']==0 for e in starts)
 assert any(e['time']==390 and e['payload']['wave']==1 for e in starts)
 assert s.ctx.state()['timeline']['done'] and str(s.session.world.resolve('boss')) in s.ctx.state()['timeline']['members']
@pytest.mark.parametrize('tick',[36,299])
def test_actual_source_onfinish_before_futurebirth_diskcp_and_head(tick,tmp_path):
 s=setup();s.session.advance(tick);p=tmp_path/'wave.json';pin=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,pin),providers=providers());s.session.advance(430-tick);r.session.advance(430-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
