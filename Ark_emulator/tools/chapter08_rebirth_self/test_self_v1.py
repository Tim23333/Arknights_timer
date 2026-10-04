import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_rebirth_self_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter08_bsnake.screen_policy_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest
OUT=ROOT/'validation/campaign/chapter08_rebirth_self_author_v1';BUFF='buff/source/bsnake/reborn_up'
def package():return json.loads((ROOT/'validation/campaign/chapter08_bsnake_rebirth_selfboost_counter_v1/report.json').read_bytes())['input']
def make(p=None):p=p or package();reg=providers();pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg);s.submit({'action':'skill','source':'player','ability':'ability/counter/kill'},at=1);return pr,s,reg

def test_actual_new_selfbuff_held_HP0_restore37500_CP75_head():
 p=package();pr,s,reg=make(p);s.advance(75);assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss');i=s.ctx.entity('boss')['components']['buffs']['instances'][0];assert i['definition']==BUFF and i['rebirth_self_lease']['rebirth_generation']==1;OUT.mkdir(parents=True,exist_ok=True);f=OUT/'source75.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h),providers=reg);s.advance(85);r.advance(85);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=reg).checkpoint();assert s.ctx.resources.current('boss','hp')==37500;(OUT/'source.trace.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2),encoding='utf8')
def test_manual_self_refresh_rejected_atomic_and_foreign_cannot_get_lease():
 pr,s,reg=make();s.advance(10);before=s.checkpoint()
 with pytest.raises(ValueError,match='internal begin'):s.ctx.buffs.apply('boss','boss',BUFF)
 assert s.checkpoint()==before;s.ctx.buffs.apply('player','boss',BUFF);instances=s.ctx.entity('boss')['components']['buffs']['instances'];assert len(instances)==1 and instances[0]['source']==s.session.world.resolve('boss')
def test_stale_generation_or_manual_world_waiting_flag_never_hold():
 pr,s,reg=make();s.advance(10);rows=s.ctx.get('boss',('buffs','instances'));rows[0]['generation']+=1;s.ctx.set('boss',('buffs','instances'),rows);s.ctx.buffs.notify('test.audit',{});assert not s.ctx.entity('boss')['components']['buffs']['instances']
 pr,s,reg=make();s.advance(10);s.ctx.rebirth.cancel(s.session.world.resolve('boss'),'test_cancel');s.ctx.buffs.notify('test.audit',{});assert not s.ctx.entity('boss')['components']['buffs']['instances']
def test_own_source_withdraw_releases_and_active_rule_false_does_not_override():
 pr,s,reg=make();s.advance(10);s.ctx.lifecycle.retire('boss','withdrawn');assert not s.ctx.entity('boss')['components']['buffs']['instances']
 p=package();p['rules'].append({'id':'rule/test/not_active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'False'}});p['buffs'][0]['active_rule']='rule/test/not_active';pr,s,reg=make(p);s.advance(160);assert s.ctx.resources.current('boss','hp')==25000

def test_failed_on_begin_callback_rolls_back_health_buff_registry_and_RNG():
 p=package();p['entities'][0]['components']['rebirth']['on_begin'].append({'op':'modify_resource','resource':'does_not_exist','delta':1,'target':'source'});pr,s,reg=make(p);s.advance(1)
 with pytest.raises(Exception):s.advance(1)
 assert s.ctx.resources.current('boss','hp')==50000 and not s.ctx.entity('boss')['components'].get('buffs',{}).get('instances');assert not s.ctx.entity('boss')['components']['runtime'].get('rebirth');assert not s.ctx.rebirth._callbacks and not getattr(s.ctx.rebirth,'_self_buff_finishing',[])

def test_repeated_legitimate_begin_refresh_sameUID_and_expiry_remove():
 p=package();p['entities'][0]['components']['rebirth']['on_begin']*=2;pr,s,reg=make(p);s.advance(10);rows=s.ctx.entity('boss')['components']['buffs']['instances'];assert len(rows)==1 and rows[0]['generation']==2 and rows[0]['rebirth_self_lease']['buff_generation']==2
 p=package();p['buffs'][0]['duration_seconds']=1;pr,s,reg=make(p);s.advance(40);assert not s.ctx.entity('boss')['components']['buffs']['instances']
