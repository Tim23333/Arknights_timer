import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter09_ordinary_independent_v2'
KEYS=['enemy_1165_duhond','enemy_1166_dusbr']
def package(key,speed=1):
 path=ROOT/'packages/campaign/chapter09_consumers/ordinary'/(key+'.module.v1.json');p=json.loads(path.read_bytes());uid=p['entities'][0]['id'];aid=p['abilities'][0]['id'];unit={'id':'unit/peer/c9/guard','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':173,'mres':91,'block_count':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'deployable':{'base_cost':11,'capacity':1,'terrain':'ground','cooldown_seconds':0},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(unit);p['entities'].append({'id':'unit/peer/c9/director','kind':'entity','components':{'spatial':{},'attributes':{'base':{'atk':1000}},'abilities':['ability/peer/c9/silence','ability/peer/c9/arts','ability/peer/c9/retire']}});p['selectors'].append({'id':'selector/peer/c9/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1});p['buffs'].append({'id':'buff/peer/c9/silence','kind':'buff','duration_seconds':.4,'selection_flags':{'abnormal_flags':[12]}})
 for name,effect in [('silence',{'op':'apply_buff','buff':'buff/peer/c9/silence'}),('arts',{'op':'damage','damage_type':'arts','scale':1,'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False}}),('retire',{'op':'retire','parameters':{'reason':'withdrawn'}})]:p['abilities'].append({'id':'ability/peer/c9/'+name,'kind':'ability','selector':'selector/peer/c9/enemy','activation':{'mode':'manual','on_start':[effect]},'timeline':[]})
 if speed!=1:p['buffs'].append({'id':'buff/peer/c9/aspeed','kind':'buff','modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':speed-1}]});p['entities'][0]['components']['buffs']['initial'].append('buff/peer/c9/aspeed')
 p['scenarioDraft']={'id':'scene/peer/c9/'+key,'ruleset':'ruleset/ark_standard','seed':91469,'map':{'rows':2,'cols':5},'resources':{'dp':{'initial':17,'capacity':99}},'objectives':{},'roster':[unit['id']],'initialEntities':[{'definition':uid,'instanceAlias':'enemy','position':{'row':0,'col':1},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':4},'checkpoints':[]}},{'definition':'unit/peer/c9/director','instanceAlias':'director','position':{'row':1,'col':0}}]};return p,aid
def make(p,deploy=True):
 pr=Compiler().compile(p);s=Engine.create(pr,seed=91469)
 if deploy:s.submit({'action':'deploy','definition':'unit/peer/c9/guard','alias':'guard','position':{'row':0,'col':1}},at=0)
 return pr,s
def proof(p,pr,s,name,split,end):
 s.advance(split);d=OUT/name;d.mkdir(parents=True,exist_ok=True);temp=Path('E:/ArkSimLogs/runs/c9_independent_v2')/name;temp.mkdir(parents=True,exist_ok=True);f=temp/'checkpoint.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h));s.advance(end-split);r.advance(end-split);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay()).checkpoint();(d/'receipt.json').write_text(json.dumps({'cp_sha':h,'checkpoint_equal':True,'head_equal':True,'time':s.session.time,'events':len(s.session.events),'input_sha':hashlib.sha256(json.dumps(p,ensure_ascii=False).encode()).hexdigest(),'event_sha':hashlib.sha256(json.dumps(list(s.session.events),default=lambda x:dict(x),ensure_ascii=False).encode()).hexdigest(),'raw_CP_cleaned_after_complete':True},indent=2),encoding='utf8');f.unlink()

@pytest.mark.parametrize('key,damage,cycle,full',[(KEYS[0],127,42,30),(KEYS[1],107,60,42)])
def test_native18_damage_differentDEF_and_fullcycle_actualpublicblock_CP11(key,damage,cycle,full):
 p,aid=package(key);pr,s=make(p);proof(p,pr,s,key+'_normal',11,150);hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['ability']==aid];assert [(e['time'],e['payload']['amount']) for e in hits]==[(t,damage) for t in range(19,150,cycle)];assert [e['time'] for e in s.session.events if e['type']=='ability.finished' and e['payload']['ability']==aid]==list(range(full+1,150,cycle));assert s.ctx.attributes.values(s.session.world.resolve('enemy'))['mres']==70

@pytest.mark.parametrize('key,damage,times,finish',[(KEYS[0],127,[16,50,84],[25,59,93]),(KEYS[1],107,[16,64],[35,83])])
def test_ASPD1_25_clock_independent_literals_CP9_head(key,damage,times,finish):
 p,aid=package(key,1.25);pr,s=make(p);proof(p,pr,s,key+'_speed',9,100);assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted' and e['payload']['ability']==aid]==[(t,damage) for t in times];assert [e['time'] for e in s.session.events if e['type']=='ability.finished' and e['payload']['ability']==aid]==finish

@pytest.mark.parametrize('key',KEYS)
def test_trueInline70RES_publicsilence6_expiry18_damage300_1000_300_CP12(key):
 p,aid=package(key);pr,s=make(p)
 for ability,t in [('arts',4),('silence',6),('arts',7),('arts',19)]:s.submit({'action':'skill','source':'director','ability':'ability/peer/c9/'+ability},at=t)
 proof(p,pr,s,key+'_silence',12,35);assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted' and e['payload']['ability']=='ability/peer/c9/arts']==[(4,300),(7,1000),(19,300)];enemy=s.ctx.entity('enemy');assert enemy['components']['attributes']['base']['mres']==0.0 and 'sp' not in enemy['components']['resources'];assert s.ctx.attributes.values(s.session.world.resolve('enemy'))['mres']==70

@pytest.mark.parametrize('key',KEYS)
def test_actual_retire_before18_prevents_damage_and_unblocked_has_no_ranged_attack(key):
 p,aid=package(key);pr,s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/peer/c9/retire'},at=9);proof(p,pr,s,key+'_retire',7,45);assert not [e for e in s.session.events if e['type']=='damage.accepted'];p,aid=package(key);pr,s=make(p,False);s.advance(40);assert not [e for e in s.session.events if e['type']=='ability.started']
