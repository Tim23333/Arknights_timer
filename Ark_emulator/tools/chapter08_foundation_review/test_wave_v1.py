import sys,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_foundation_review.fixtures_v1 import package,effect
OUT=ROOT/'validation/campaign/chapter08_foundation_independent_v1'
def make(p):pr=Compiler().compile(p);s=Engine.create(pr,seed=91947);s.submit({'action':'skill','source':'director','ability':'ability/peer/foundation/kill'},at=6);return pr,s
def proof(pr,s,p,name,split,end):
 s.advance(split);d=OUT/name;d.mkdir(parents=True,exist_ok=True);f=d/'checkpoint.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h));s.advance(end-split);r.advance(end-split);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay()).checkpoint();(d/'evidence.json').write_text(json.dumps({'input':p,'cp_sha':h,'checkpoint':s.checkpoint()},indent=2),encoding='utf8')

def test_new_quantities_HP0alive_transfer20_birth3_16_27_upgrade_and_CP13_head():
 p=package(upgrade=True);pr,s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/peer/foundation/retire'},at=53);s.advance(21);assert s.ctx.alive('source') and not s.ctx.active('source') and s.ctx.resources.current('source','hp')==0;assert s.ctx.state()['timeline']['members']['3']['wave']==1 and s.ctx.state()['timeline']['members']['4']['wave']==0;pr,s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/peer/foundation/retire'},at=53);proof(pr,s,p,'newnumbers_upgrade',13,65);assert s.ctx.resources.current('director','probe')==26;assert [e['time'] for e in s.session.events if e['type']=='timeline.source_transferred']==[20];assert [e['time'] for e in s.session.events if e['type']=='entity.created' and e['payload']['definition']!='unit/peer/foundation/director']==[3,16,27];assert len([e for e in s.session.events if e['type']=='timeline.finish_requested'])==1

def test_joint_fork_reaction_latefault_rolls_back_body_allstores_but_transfer_committed():
 pr,s=make(package(fault=True));s.advance(19);before=s.checkpoint()
 with pytest.raises(Exception):s.advance(4)
 after=s.checkpoint();assert s.ctx.resources.current('director','probe')==17 and s.ctx.state()['timeline']['members']['3']['wave']==1;assert len([e for e in s.session.events if e['type']=='timeline.source_transferred'])==1 and not [e for e in s.session.events if e['type']=='peer.foundation.beforefault'];assert after['kernel']['random']==before['kernel']['random'];assert not [t for t in s.session.scheduler.pending if t['kind']=='event_reaction' and t['payload']['event']=='peer.foundation.beforefault'];assert after['kernel']['failure'] is not None
 with pytest.raises(RuntimeError):s.advance(1)
 d=OUT/'latefault';d.mkdir(parents=True,exist_ok=True);(d/'actual.json').write_text(json.dumps({'before':before,'failed_after':after,'no_failed_replay_claim':True},indent=2),encoding='utf8')

def test_true_not_downgraded_foreign_current_member_rejected_and_no_actorclone():
 p=package();p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][1]['delay_seconds']=5/30;late=dict(p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][1]);late['delay_seconds']=13/30;late['spawn']=dict(late['spawn'],instanceAlias='late');p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'].append(late);pr,s=make(p);s.advance(12);before=s.checkpoint();assert s.ctx.timeline.finish_current('source',effect(False)) is False;assert s.checkpoint()==before;assert s.ctx.timeline.finish_current('old',effect(True)) is False;assert s.ctx.state()['timeline']['tracking_requests']['0']['source']==3

def test_typed_fp_and_public_checkpoint_bool_quantum_and_generation_are_not_numbers():
 p=package();pr,s=make(p);s.advance(13);cp=s.checkpoint();bad=json.loads(json.dumps(cp));bad['kernel']['quantum']=True
 with pytest.raises(ValueError):Engine.restore(pr,bad)
 bad=json.loads(json.dumps(cp));bad['runtime_fingerprint']=False
 with pytest.raises(ValueError):Engine.restore(pr,bad)
