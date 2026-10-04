import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_terminal_lifecycle_v2_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.terminal_lifecycle import valid
from tools.chapter08_terminal_lifecycle.test_terminal_source_v1 import package,providers
from ark_sim.tools.replay import replay
import pytest
BUFF='buff/test/terminal/finish';OUT=ROOT/'validation/campaign/chapter08_terminal_completion_v3'
def make(*,fault=False,duration=2):
 p=package();cfg=p['entities'][0]['components']['rebirth'];spec=cfg['zero_restore_lifecycle'];cfg['retain_buffs'].append(BUFF);spec['retained_buffs'].append(BUFF);spec['completion_buffs']=[BUFF];spec['on_enter']=[{'op':'apply_buff','target':'source','buff':BUFF}];p['buffs'].append({'id':BUFF,'kind':'buff','duration_seconds':duration,'on_remove':([{'op':'modify_resource','target':'source','resource':'not_real','delta':1}] if fault else [])+[{'op':'instant_kill','target':'source','parameters':{'cause':'source_final_end','skip_rebirth':False}}]});reg=providers();pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg,seed=817);s.submit({'action':'skill','source':'player','ability':'ability/counter/kill'},at=1);s.submit({'action':'skill','source':'player','ability':'ability/counter/kill'},at=160);return pr,s,reg,p

def test_real_on_remove_expiry_skip_rebornFalse_end_once_CPP_head():
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 pr,s,reg,p=make();s.advance(340);assert valid(s.ctx,s.session.world.resolve('boss'));OUT.mkdir(parents=True,exist_ok=True);f=OUT/'terminal340.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h),providers=reg);s.advance(50);r.advance(50);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=reg).checkpoint();assert not s.ctx.alive('boss');ends=[e for e in s.session.events if e['type']=='entity.terminal.completed'];assert len(ends)==1 and ends[0]['time']==370 and ends[0]['payload']['reason']=='owned_buff_finished';assert len([e for e in s.session.events if e['type']=='combat.kill' and e['payload']['target']==2])==1;(OUT/'source.json').write_text(json.dumps({'core':pr.implementation_fingerprint if hasattr(pr,'implementation_fingerprint') else None,'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2),encoding='utf8')

def test_early_remove_cannot_claim_completion():
 pr,s,reg,p=make();s.advance(320);s.ctx.buffs.remove('boss',BUFF);assert s.ctx.alive('boss') and valid(s.ctx,s.session.world.resolve('boss'));assert not [e for e in s.session.events if e['type']=='entity.terminal.completed']

def test_manual_refresh_cannot_borrow_realUID_generation():
 pr,s,reg,p=make();s.advance(320);s.ctx.buffs.apply('boss','boss',BUFF);s.advance(80);assert s.ctx.alive('boss') and not [e for e in s.session.events if e['type']=='entity.terminal.completed']

def test_onremove_failure_rolls_back_death_job_and_private_scope():
 pr,s,reg,p=make(fault=True);s.advance(370)
 with pytest.raises(Exception):s.advance(1)
 assert s.ctx.alive('boss') and s.ctx.resources.current('boss','hp')==0 and valid(s.ctx,s.session.world.resolve('boss'));assert not getattr(s.ctx.rebirth,'_terminal_removing',[]);assert not [e for e in s.session.events if e['type']=='entity.terminal.completed']

def test_exact_deadline_expire_precedes_finite_fallback():
 pr,s,reg,p=make(duration=28);s.advance(1151);ends=[e for e in s.session.events if e['type']=='entity.terminal.completed'];assert len(ends)==1 and ends[0]['time']==1150 and ends[0]['payload']['reason']=='owned_buff_finished'
