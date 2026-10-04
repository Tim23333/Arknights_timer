import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.build_chapter04_demon_profiles import build,UID,OUT
CAPTURES=[]
def create(policy,offpath=False):
 path=OUT/(policy+'.model.json');raw=path.read_bytes();p=json.loads(raw);assert p==build(policy)
 guard={'id':'unit/demon_guard','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':20000,'def':157,'block_count':1}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'deployable':{'base_cost':5,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(guard)
 p['scenarioDraft']={'id':'scene/demon_branch','ruleset':'ruleset/ark_standard','roster':['unit/demon_guard'],'resources':{'dp':{'initial':20,'capacity':20},'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'},'map':{'rows':3,'cols':5},'waves':[{'at':0,'definition':UID,'instanceAlias':'demon','position':{'row':1,'col':0},'route':{'motionMode':0,'startPosition':{'row':1,'col':0},'endPosition':{'row':1,'col':4},'checkpoints':[]}}]}
 fr=(json.dumps(p,indent=2)+'\n').encode();s=Engine.create(Compiler().compile(json.loads(fr)),seed=404010);s.submit({'action':'deploy','entity':'unit/demon_guard','alias':'guard','position':{'row':0 if offpath else 1,'col':0}},at=4);return s,{'package_sha256':hashlib.sha256(raw).hexdigest(),'fixture_sha256':hashlib.sha256(fr).hexdigest(),'fixture':json.loads(fr),'seed':404010}
def capture(s,inputs,tmp,expected):
 s.advance(70);sha=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',sha));s.advance(65);r.advance(65);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();CAPTURES.append({'input':inputs,'expected':expected,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay(),'checkpoint_sha256':sha,'checkpoint_equal':True,'commands_replay_equal':True})
@pytest.mark.parametrize('policy,frame,end',[('with_pre_only',27,45),('no_pre_only',15,33)])
def test_explicit_branch_public_block_damage_frame_shared_interval(policy,frame,end,tmp_path):
 s,inputs=create(policy);capture(s,inputs,tmp_path,{'ATK':600,'DEF':157,'damage':443,'packet_offset':frame,'branch_end_offset':end,'interval':60})
 ref=s.session.world.resolve('demon');guard=s.session.world.resolve('guard');starts=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==ref];hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==ref];fin=[e for e in s.session.events if e['type']=='ability.finished' and e['payload']['source']==ref]
 assert [e['time'] for e in starts[:3]]==[5,65,125];assert [e['time']-starts[i]['time'] for i,e in enumerate(hits)]==[frame]*len(hits);assert all(e['payload']['amount']==443 and e['payload']['target']==guard for e in hits);assert fin[0]['time']-starts[0]['time']==end
 assert s.ctx.resources.current('demon','hp')==7500 and s.ctx.spatial.blocked_by(ref)==guard
@pytest.mark.parametrize('policy',['with_pre_only','no_pre_only'])
def test_offpath_near_guard_is_not_synthetic_combat_target(policy,tmp_path):
 s,inputs=create(policy,True);capture(s,inputs,tmp_path,{'offpath_guard_should_receive':0})
 ref=s.session.world.resolve('demon');assert not any(e['type']=='damage.accepted' and e['payload']['source']==ref for e in s.session.events);assert s.ctx.resources.current('guard','hp')==20000
@pytest.mark.parametrize('bad',[None,'first_with_pre_then_no_pre','guess'])
def test_unknown_or_dynamic_dispatch_not_silently_defaulted(bad):
 with pytest.raises(ValueError,match='Explicit known'):build(bad)
