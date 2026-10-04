import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m74_death_claim_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def fixture():return json.loads((ROOT/'validation/campaign/m61_roster_peer/initial_review.json').read_bytes())['fixtures'][-1]['input']['fixture']
def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=610031)
def kills(s):return [e for e in s.session.events if e['type']=='combat.kill']
def test_original_peer_real_nested_instantkill_is_single_actual_executor_disk_replay(tmp_path):
 s=make();s.submit({'action':'skill','source':'hero','ability':'ability/damage'},at=1);s.advance(1);path=tmp_path/'cp.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,h));s.advance(5);r.advance(5)
 assert s.ctx.state()['kills']==1 and len(kills(s))==1 and kills(s)[0]['payload']['source']==s.session.world.resolve('boss')
 assert s.ctx.get('boss',('runtime','death_generation'))==1 and s.ctx.get('boss',('runtime','combat_death_claim'))['payload']['source']==s.session.world.resolve('boss')
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_repeated_retire_damage_and_claim_do_not_add_generation_or_reward():
 s=make();s.submit({'action':'skill','source':'hero','ability':'ability/damage'},at=1);s.advance(2);before=len(kills(s));s.ctx.lifecycle.retire('boss','dead');s.ctx.effects.execute('hero',['boss'],{'op':'damage','damage_type':'true'});s.ctx.effects.execute('hero',['boss'],{'op':'instant_kill','parameters':{'cause':'again','skip_rebirth':True}})
 assert s.ctx.lifecycle.claim_combat_kill('boss',{'source':s.session.world.resolve('hero'),'ability':None,'cast':None}) is None
 assert s.ctx.get('boss',('runtime','death_generation'))==1 and s.ctx.state()['kills']==1 and len(kills(s))==before==1
def test_normal_lethal_damage_claim_source_is_hero_and_no_first_down_claim():
 p=fixture();p['entities'][0]['components']['rebirth']['on_begin']=[];s=make(p);s.submit({'action':'skill','source':'hero','ability':'ability/damage'},at=1);s.advance(2);assert not kills(s) and s.ctx.get('boss',('runtime','death_generation')) is None
 s.advance(6);s.ctx.effects.execute('hero',['boss'],{'op':'damage','damage_type':'true'});assert len(kills(s))==1 and kills(s)[0]['payload']['source']==s.session.world.resolve('hero')
def test_new_real_transition_rejects_stale_generation_and_allows_exact_epoch():
 s=make();s.ctx.lifecycle.retire('boss','dead');s.ctx.lifecycle.claim_combat_kill('boss',{'source':None,'source_policy':'none','origin':{'kind':'test'}},generation=1)
 # Isolated direct lifecycle API fixture: explicitly reenable the same actor,
 # rather than pretending this API-only mutation is a public command replay.
 s.ctx.set('boss',('runtime','alive'),True);s.ctx.set('boss',('runtime','active'),True);s.ctx.set('boss',('runtime','state'),'alive');s.ctx.lifecycle.retire('boss','dead')
 assert s.ctx.get('boss',('runtime','death_generation'))==2
 assert s.ctx.lifecycle.claim_combat_kill('boss',{'source':s.session.world.resolve('hero')},generation=1) is None
 assert s.ctx.lifecycle.claim_combat_kill('boss',{'source':None,'source_policy':'none','origin':{'kind':'test2'}},generation=2) is not None
 assert [e['payload']['source'] for e in kills(s)]==[None,None]
def test_source_free_payload_keeps_none_and_origin_and_refuses_fake_actor():
 s=make();s.ctx.lifecycle.retire('boss','dead');before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.lifecycle.claim_combat_kill('boss',{'source_policy':'none','source':s.session.world.resolve('hero'),'origin':{'kind':'tile'}})
 assert s.checkpoint()==before
 payload={'source':None,'source_policy':'none','origin':{'kind':'tile','row':0,'col':0},'ignore_for_sp':True,'ability':None,'cast':None};s.ctx.lifecycle.claim_combat_kill('boss',payload,generation=1);assert kills(s)[0]['payload']['source'] is None and dict(kills(s)[0]['payload']['origin'])==payload['origin']
def test_real_kill_emit_toggle_callback_failure_restores_whole_damage_transaction():
 p=fixture();p['entities'][0]['components']['rebirth']['max_count']=0;p.setdefault('buffs',[]).extend([{'id':'buff/killwatch','kind':'buff','toggle':{'rule':'rule/fail','buff':'buff/child','initial_enabled':False,'restore_delay_seconds':1,'events':[{'event':'combat.kill','owner_role':'source'}]}},{'id':'buff/child','kind':'buff','stacking':{'mode':'independent'}}]);p['rules'].append({'id':'rule/fail','kind':'rule','contract':'passive.toggle','implementation':{'type':'expression','expression':'False if inputs.state.last_pulse == None else 1/0'}});p['entities'][1]['components'].setdefault('buffs',{})['initial']=['buff/killwatch'];s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.effects.execute('hero',['boss'],{'op':'random','stream':'peer','probability':1,'on_success':[{'op':'damage','damage_type':'true'}]})
 assert s.checkpoint()==before and not s.ctx.rebirth._requests and not s.ctx.buffs.toggles._busy

def test_public_against_dead_target_cannot_add_actor_reward():
 s=make()
 for at in (1,3,5):s.submit({'action':'skill','source':'hero','ability':'ability/damage'},at=at)
 s.advance(8);assert s.ctx.state()['kills']==1 and len(kills(s))==1 and s.ctx.get('boss',('runtime','death_generation'))==1
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
