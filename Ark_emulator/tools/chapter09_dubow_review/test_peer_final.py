import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_bsnake_combat.policies_v1 import providers
REG=providers(); MODULE=ROOT/'packages/campaign/chapter09_consumers/ordinary/enemy_1167_dubow.module.v1.json'
def make(speed=1,retire=None,state=None,col=1):
 p=json.loads(MODULE.read_bytes());uid=p['entities'][0]['id'];aid=p['abilities'][0]['id']
 p['entities'].append({'id':'unit/peer/dubow/guard','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':9000,'def':193,'mres':87}},'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'}},'spatial':{},'selection_state':state or {'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
 if speed!=1:p['buffs'].append({'id':'buff/peer/dubow/as','kind':'buff','modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':speed-1}]});p['entities'][0]['components']['buffs']['initial'].append('buff/peer/dubow/as')
 p['scenarioDraft']={'id':'scene/peer/dubow','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':5},'objectives':{},'initialEntities':[{'definition':uid,'instanceAlias':'enemy','position':{'row':0,'col':0}},{'definition':'unit/peer/dubow/guard','instanceAlias':'guard','position':{'row':0,'col':col}}]}
 pr=Compiler(providers=REG).compile(p);s=Engine.create(pr,providers=REG,seed=79313)
 if retire is not None:s.submit({'action':'withdraw','source':'enemy'},at=retire)
 return p,pr,s,aid

def proof(p,pr,s,name,split=22,end=50):
 s.advance(split);temp=Path('E:/ArkSimLogs/runs/c9_dubow_peer')/(name+'.json');temp.parent.mkdir(parents=True,exist_ok=True);h=write_ordered(temp,s.checkpoint());r=Engine.restore(pr,load_bound(temp,h),providers=REG);s.advance(end-split);r.advance(end-split);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=REG).checkpoint();out=ROOT/'validation/campaign/chapter09_dubow_independent_final_cases'/name;out.mkdir(parents=True,exist_ok=True);(out/'receipt.json').write_text(json.dumps({'cp_sha':h,'events':len(s.session.events),'time':s.session.time,'CP_and_head_equal':True,'CP_deleted_after_verification':True,'input_sha':hashlib.sha256(json.dumps(p).encode()).hexdigest()},indent=2));temp.unlink()

def test_differentDEF193_RES87_launch21_travel3_physical57_CP22_head():
 p,pr,s,aid=make();proof(p,pr,s,'normal');assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(24,57)];assert [e['time'] for e in s.session.events if e['type']=='ability.finished' and e['payload']['ability']==aid]==[45]

def test_ASPD1_5_launch14_full30_recovery46_CP15_head():
 p,pr,s,aid=make(1.5);proof(p,pr,s,'speed',15,80);assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(17,57),(63,57)];assert [e['time'] for e in s.session.events if e['type']=='ability.finished' and e['payload']['ability']==aid]==[30,76]

@pytest.mark.parametrize('state,col',[({'side':0,'motion':2,'category':1,'unit_type':1},1),({'side':0,'motion':1,'category':1,'unit_type':1,'camouflage':True},1),({'side':0,'motion':1,'category':1,'unit_type':1,'target_free':True},1),({'side':0,'motion':1,'category':1,'unit_type':1},3)])
def test_native_qualification_rejects_fly_camo_free_outside_radius(state,col):
 p,pr,s,aid=make(state=state,col=col);s.advance(50);assert not [e for e in s.session.events if e['type']=='ability.started' or e['type']=='damage.accepted']

def test_public_source_retire22_keeps_launched_arrow_CP23_head():
 p,pr,s,aid=make();p['selectors'].append({'id':'selector/peer/archer','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1});p['abilities'].append({'id':'ability/peer/retire','kind':'ability','selector':'selector/peer/archer','activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdrawn'}}]},'timeline':[]});p['entities'].append({'id':'unit/peer/director','kind':'entity','components':{'abilities':['ability/peer/retire'],'spatial':{}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/director','instanceAlias':'director','position':{'row':1,'col':4}});pr=Compiler(providers=REG).compile(p);s=Engine.create(pr,providers=REG,seed=79313);s.submit({'action':'skill','source':'director','ability':'ability/peer/retire'},at=22);proof(p,pr,s,'launched_retire',23,50);assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(24,57)];assert not s.ctx.alive('enemy')

def test_raw_radius_projectile_and_shared_owned_node_source_fields():
 p=json.loads(MODULE.read_bytes());locks=p['manifest']['metadata']['source_locks'];assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==h for path,h in locks.items());raw=json.loads((ROOT/'packages/campaign/chapter09_source_prepare/dubow.range.supplement.v1.json').read_bytes());assert raw['exactRadius']==p['selectors'][0]['region']['radius']==2.0
 assert len(p['abilities'])==len(p['entities'][0]['components']['abilities'])==1;assert p['abilities'][0]['metadata']['source_OnAttack_frame']==21 and p['abilities'][0]['metadata']['source_full_frame']==45
 comp=p['projectiles'][0]['metadata']['native_projectile']['components'];m=next(c['raw'] for c in comp.values() if c['native_class']=='AdvancedMovement');q=next(c['raw'] for c in comp.values() if c['native_class']=='SimpleProjectile');assert m['_speed']==10 and q['_lifeTime']==5 and q['_maxHitNum']==1 and q['_stopWhenSourceInvalid']==0;assert p['entities'][0]['components']['attributes']['base']['atk']==250 and p['entities'][0]['components']['attributes']['base']['attack_interval']==2.3
