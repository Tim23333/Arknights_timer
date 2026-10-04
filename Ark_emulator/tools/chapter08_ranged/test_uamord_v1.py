import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_selection_context_clock_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from tools.chapter08_ranged.policies_secondary_v1 import providers
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter08_uamord_author_v1';MARKER='buff/ch8/source/mark_neutral[effect]'
def package(two=False,block=False):
 p=json.loads((ROOT/'packages/campaign/chapter08_consumers/ranged/uamord.module.v3.json').read_bytes());u=p['entities'][0]['id'];p['entities'].append({'id':'unit/mage/test/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':911,'mres':65,'block_count':1,'taunt_level':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'buffs':{'initial':[]},'deployable':{'base_cost':1,'terrain':'ground','capacity':1,'cooldown_seconds':0},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']={'id':'scene/ch8/mage','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'objectives':{},'resources':{'dp':{'initial':10,'capacity':99}},'roster':['unit/mage/test/player'],'initialEntities':[{'definition':u,'instanceAlias':'source','position':{'row':1,'col':1}}]}
 if block:p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':'WALK','startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':4},'checkpoints':[]}
 else:p['scenarioDraft']['initialEntities'].append({'definition':'unit/mage/test/player','instanceAlias':'target','position':{'row':1,'col':2}})
 if two:
  marked=json.loads(json.dumps(p['entities'][-1]));marked['id']='unit/mage/test/marked';marked['components']['buffs']['initial']=[MARKER];p['entities'].append(marked);p['scenarioDraft']['initialEntities'].append({'definition':marked['id'],'instanceAlias':'marked','position':{'row':1,'col':3}})
 return p

def make(p):r=providers();pr=Compiler(providers=r).compile(p);return pr,Engine.create(pr,providers=r),r
def hits(s):return [(e['time'],e['payload']['target'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']
def cp(p,s,pr,r,t,end,label):
 s.advance(t);OUT.mkdir(parents=True,exist_ok=True);f=OUT/(label+'.cp.json');assert not f.exists();h=write_ordered(f,s.checkpoint());b=Engine.restore(pr,load_bound(f,h),providers=r);s.advance(end-t);b.advance(end-t);assert s.checkpoint()==b.checkpoint()==replay(pr,s.export_replay(),providers=r).checkpoint();(OUT/(label+'.trace.json')).write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2),encoding='utf8')

def test_source_single_arts19_84_speed10_RES65_DEF911_119_CP20():
 p=package();pr,s,r=make(p);cp(p,s,pr,r,20,120,'arts20');assert hits(s)==[(22,3,119.00000000000001),(106,3,119.00000000000001)]
def test_same_native_ranged_pointer_blockedcombat_overrides_marked_far():
 p=package(True,True);pr,s,r=make(p);s.submit({'action':'deploy','entity':'unit/mage/test/player','alias':'target','row':1,'col':1},at=0);cp(p,s,pr,r,10,110,'block10');target=s.session.world.resolve('target');assert all(i==target for _,i,_ in hits(s));assert hits(s)==[(21,target,119.00000000000001),(105,target,119.00000000000001)]
def test_secondary_SPECIFIED_BUFF3_tie_preference_and_taunt_last_policy():
 p=package(True);_,s,_=make(p);s.advance(45);assert hits(s)==[(25,4,119.00000000000001)]
 p=package(True);p['entities'][1]['components']['attributes']['base']['taunt_level']=20;_,s,_=make(p);s.advance(35);assert hits(s)==[(22,3,119.00000000000001)]
def test_currentRES75_before_hit_and_ASPD2():
 p=package();p['buffs'].append({'id':'buff/mage/RES','kind':'buff','duration_seconds':2,'modifiers':[{'attribute':'mres','layer':'flat','value':10}]});p['selectors'].append({'id':'selector/test/player','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':3}}]});p['scenarioDraft']['scheduledEffects']=[{'at':20,'effect':{'op':'apply_buff','buff':'buff/mage/RES','selector':'selector/test/player'}}];pr,s,r=make(p);cp(p,s,pr,r,19,35,'RES19');assert hits(s)==[(22,3,85)]
 p=package();p['buffs'].append({'id':'buff/mage/ASPD','kind':'buff','duration_seconds':2,'modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':1}]});p['selectors'].append({'id':'selector/test/self','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':2}}]});p['scenarioDraft']['scheduledEffects']=[{'at':0,'effect':{'op':'apply_buff','buff':'buff/mage/ASPD','selector':'selector/test/self'}}];_,s,_=make(p);s.advance(60);assert hits(s)==[(13,3,119.00000000000001),(55,3,119.00000000000001)]
def test_typed_fly_camo_free_range_reject_both_marker_and_normal():
 for flag,val in [('target_free',True),('camouflage',True),('motion',2),('side',1),('category',4)]:
  p=package();p['entities'][-1]['components']['selection_state'][flag]=val;_,s,_=make(p);s.advance(35);assert not hits(s)
 p=package();p['scenarioDraft']['initialEntities'][1]['position']['col']=3.200001;_,s,_=make(p);s.advance(35);assert not hits(s)
