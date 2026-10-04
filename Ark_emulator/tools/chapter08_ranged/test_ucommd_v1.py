import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_selection_context_clock_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from tools.chapter08_ranged.policies_v1 import providers
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
MARKER='buff/ch8/source/mark_neutral[effect]';OUT=ROOT/'validation/campaign/chapter08_ucommd_author_v1'
def package(marked=True,block=False):
 p=json.loads((ROOT/'packages/campaign/chapter08_consumers/ranged/ucommd.module.v1.json').read_bytes());u=p['entities'][0]['id'];p['entities'].append({'id':'unit/ch8/test/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':111,'mres':88,'block_count':2}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'buffs':{'initial':[MARKER] if marked else []},'spatial':{},'deployable':{'base_cost':1,'capacity':1,'terrain':'ground','cooldown_seconds':0},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']={'id':'scene/ucommd/source','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'resources':{'dp':{'initial':10,'capacity':99}},'roster':['unit/ch8/test/player'],'objectives':{},'initialEntities':[{'definition':u,'instanceAlias':'source','position':{'row':1,'col':1}}]}
 if block:p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':'WALK','startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':4},'checkpoints':[]}
 else:p['scenarioDraft']['initialEntities'].append({'definition':'unit/ch8/test/player','instanceAlias':'target','position':{'row':1,'col':2}})
 return p

def make(p):reg=providers();program=Compiler(providers=reg).compile(p);return program,Engine.create(program,providers=reg),reg
def hits(s):return [e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['target']==s.session.world.resolve('target')]
def save_cp(p,s,program,reg,at,end,label):
 s.advance(at);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/(label+'.cp.json');assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(end-at);r.advance(end-at);assert s.checkpoint()==r.checkpoint()==replay(program,s.export_replay(),providers=reg).checkpoint();(OUT/(label+'.trace.json')).write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2),encoding='utf8')

def test_unblocked_marked_ranged15_60clock_speed10_219_and_CP16():
 p=package();program,s,reg=make(p);save_cp(p,s,program,reg,18,100,'ranged18');assert [(e['time'],e['payload']['amount']) for e in hits(s)]==[(20,439),(86,439)];assert [e['time'] for e in s.session.events if e['type']=='projectile.launched']==[17,83];assert set(s.ctx.entity('source')['components']['resources'])=={'hp'};assert s.ctx.entity('source')['components']['selection_state']['abnormal_immunes']==()
def test_real_blocked_combat_unmarked_player_publicDP1_CP9():
 p=package(False,True);program,s,reg=make(p);s.submit({'action':'deploy','entity':'unit/ch8/test/player','alias':'target','row':1,'col':1},at=0);save_cp(p,s,program,reg,9,100,'combat9');assert [(e['time'],e['payload']['amount']) for e in hits(s)]==[(19,439),(85,439)];assert not [e for e in s.session.events if e['type']=='projectile.launched'];assert s.ctx.resources.current('system/battle','dp')==9
def test_source_marker_eligibility_and_typed_status_range_reject():
 for flag,value in [('target_free',True),('camouflage',True),('motion',2),('side',1),('category',4)]:
  p=package();p['entities'][-1]['components']['selection_state'][flag]=value;_,s,_=make(p);s.advance(25);assert not hits(s)
 p=package(False);_,s,_=make(p);s.advance(25);assert not hits(s)
 p=package();p['scenarioDraft']['initialEntities'][1]['position']['col']=2.200001;_,s,_=make(p);s.advance(25);assert not hits(s)
def test_current_DEF_before_hit_and_public_ASPD2():
 p=package();p['buffs'].append({'id':'buff/test/DEF','kind':'buff','duration_seconds':2,'modifiers':[{'attribute':'def','layer':'flat','value':100}]});p['selectors'].append({'id':'selector/test/player','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':3}}]});p['scenarioDraft']['scheduledEffects']=[{'at':16,'effect':{'op':'apply_buff','buff':'buff/test/DEF','selector':'selector/test/player'}}];program,s,reg=make(p);save_cp(p,s,program,reg,15,30,'DEF15');assert [(e['time'],e['payload']['amount']) for e in hits(s)]==[(20,339)]
 p=package();p['buffs'].append({'id':'buff/test/ASPD','kind':'buff','duration_seconds':2,'modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':1}]});p['selectors'].append({'id':'selector/test/source','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':2}}]});p['scenarioDraft']['scheduledEffects']=[{'at':0,'effect':{'op':'apply_buff','buff':'buff/test/ASPD','selector':'selector/test/source'}}];_,s,_=make(p);s.advance(50);assert [(e['time'],e['payload']['amount']) for e in hits(s)]==[(12,439),(45,439)]
def test_capture_marker_remove_after_launch_retains_hit_then_future_reject():
 p=package();p['selectors'].append({'id':'selector/test/player','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':3}}]});p['scenarioDraft']['scheduledEffects']=[{'at':18,'effect':{'op':'remove_buff','buff':MARKER,'selector':'selector/test/player'}}];program,s,reg=make(p);save_cp(p,s,program,reg,18,100,'remove18');assert [(e['time'],e['payload']['amount']) for e in hits(s)]==[(20,439)]
