import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_rebirth_self_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter08_bsnake.screen_policy_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest
OUT=ROOT/'validation/campaign/chapter08_rebirth_self_author_v4';BUFF='buff/source/bsnake/reborn_up'
def package():return json.loads((ROOT/'validation/campaign/chapter08_bsnake_rebirth_selfboost_counter_v1/report.json').read_bytes())['input']
def make(p=None):p=p or package();reg=providers();pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg);s.submit({'action':'skill','source':'player','ability':'ability/counter/kill'},at=1);return pr,s,reg

def test_actual_new_selfbuff_held_HP0_restore37500_CP75_head():
 p=package();pr,s,reg=make(p);s.advance(75);assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss');i=s.ctx.entity('boss')['components']['buffs']['instances'][0];assert i['definition']==BUFF and i['rebirth_self_lease']['rebirth_generation']==1;OUT.mkdir(parents=True,exist_ok=True);f=OUT/'source75.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h),providers=reg);s.advance(85);r.advance(85);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=reg).checkpoint();assert s.ctx.resources.current('boss','hp')==37500;(OUT/'source.trace.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2),encoding='utf8')
def test_manual_self_refresh_rejected_atomic_and_foreign_cannot_get_lease():
 pr,s,reg=make();s.advance(10);before=s.checkpoint()
 with pytest.raises(ValueError,match='internal begin'):s.ctx.buffs.apply('boss','boss',BUFF)
 assert s.checkpoint()==before;s.ctx.buffs.apply('player','boss',BUFF);s.ctx.buffs.notify('test.audit',{});instances=s.ctx.entity('boss')['components']['buffs']['instances'];assert len(instances)==1 and instances[0]['source']==s.session.world.resolve('boss')
def test_stale_generation_or_manual_world_waiting_flag_never_hold():
 pr,s,reg=make();s.advance(10);rows=s.ctx.get('boss',('buffs','instances'));rows[0]['generation']+=1;s.ctx.set('boss',('buffs','instances'),rows);s.ctx.buffs.notify('test.audit',{});assert not s.ctx.entity('boss')['components']['buffs']['instances']
 pr,s,reg=make();s.advance(10);s.ctx.rebirth.cancel(s.session.world.resolve('boss'),'test_cancel');s.ctx.buffs.notify('test.audit',{});assert not s.ctx.entity('boss')['components']['buffs']['instances']
def test_own_source_withdraw_releases_and_active_rule_false_does_not_override():
 pr,s,reg=make();s.advance(10);s.ctx.lifecycle.retire('boss','withdrawn');s.ctx.buffs.notify('test.audit',{});assert not s.ctx.entity('boss')['components']['buffs']['instances']
 p=package();p['rules'].append({'id':'rule/test/not_active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'False'}});p['buffs'][0]['active_rule']='rule/test/not_active';pr,s,reg=make(p);s.advance(160);assert s.ctx.resources.current('boss','hp')==25000

def test_failed_on_begin_callback_rolls_back_health_buff_registry_and_RNG():
 p=package();p['entities'][0]['components']['rebirth']['on_begin'].append({'op':'modify_resource','resource':'does_not_exist','delta':1,'target':'source'});pr,s,reg=make(p);s.advance(1)
 with pytest.raises(Exception):s.advance(1)
 assert s.ctx.resources.current('boss','hp')==50000 and not s.ctx.entity('boss')['components'].get('buffs',{}).get('instances');assert not s.ctx.entity('boss')['components']['runtime'].get('rebirth');assert not s.ctx.rebirth._callbacks and not getattr(s.ctx.rebirth,'_self_buff_finishing',[])

def test_repeated_legitimate_begin_refresh_sameUID_and_expiry_remove():
 p=package();p['entities'][0]['components']['rebirth']['on_begin']*=2;pr,s,reg=make(p);s.advance(10);rows=s.ctx.entity('boss')['components']['buffs']['instances'];assert len(rows)==1 and rows[0]['generation']==2 and rows[0]['rebirth_self_lease']['buff_generation']==2
 p=package();p['buffs'][0]['duration_seconds']=1;pr,s,reg=make(p);s.advance(40);assert not s.ctx.entity('boss')['components']['buffs']['instances']


def test_finished_source_tag_cannot_be_borrowed_by_forged_completing_world_flags():
 from ark_sim.domains.rebirth_self_buffs import retained
 pr,s,reg=make();s.advance(160);rows=s.ctx.get('boss',('buffs','instances'));assert rows;s.ctx.set('boss',('runtime','active'),False);s.ctx.set('boss',('runtime','state'),'rebirth');state=s.ctx.get('boss',('runtime','rebirth'));state['phase']='completing';s.ctx.set('boss',('runtime','rebirth'),state);spec=s.ctx.get('boss',('resources','hp'));spec['current']=0;s.ctx.set('boss',('resources','hp'),spec);assert not retained(s.ctx,rows[0]);s.ctx.buffs.notify('test.audit',{});assert not s.ctx.entity('boss')['components']['buffs']['instances']

def test_current_finish_callback_fault_clears_internal_finish_scope_and_rolls_back():
 p=package();p['entities'][0]['components']['rebirth']['on_finish']=[{'op':'modify_resource','resource':'not_real','delta':1,'target':'source'}];pr,s,reg=make(p);s.advance(151)
 with pytest.raises(Exception):s.advance(1)
 assert s.ctx.resources.current('boss','hp')==0 and s.ctx.get('boss',('runtime','rebirth','phase'))=='waiting';assert not getattr(s.ctx.rebirth,'_self_buff_finishing',[]) and not s.ctx.rebirth._callbacks

def test_rebinding_second_actual_rebirth_refreshes_real_incarnation_not_old_generation():
 p=package();p['rules'][0:0]=[];next(r for r in p['rules'] if r['id']=='rule/bsnake/source_restore')['implementation']['expression']='inputs.parameters.capacity * inputs.parameters.ratio';p['entities'][0]['components']['rebirth']['on_begin'][0].pop('condition');pr,s,reg=make(p);s.submit({'action':'skill','source':'player','ability':'ability/counter/kill'},at=160);s.advance(170);rows=s.ctx.entity('boss')['components']['buffs']['instances'];assert len(rows)==1 and rows[0]['rebirth_self_lease']['rebirth_generation']==2 and s.ctx.resources.current('boss','hp')==0;s.advance(150);assert s.ctx.resources.current('boss','hp')==37500

def test_periodic_retained_stats_stay_but_lease_never_grants_undeclared_cast():
 p=package();p['buffs'][0]['interval_seconds']=1;p['buffs'][0]['effects']=[];pr,s,reg=make(p);s.advance(100);assert len(s.ctx.entity('boss')['components']['buffs']['instances'])==1;s.submit({'action':'skill','source':'boss','ability':'ability/ch8/bsnake/firecommon'},at=101);s.advance(3);assert any(e['type']=='command.rejected' and e['time']==101 for e in s.session.events);assert not [e for e in s.session.events if e['type']=='projectile.launched']
