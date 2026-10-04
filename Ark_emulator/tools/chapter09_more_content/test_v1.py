"""Actual numeric attacks, source aura qualifications and ordered CP/head."""
from tools.chapter09_more_content.build_v1 import ROOT,OUT,KEYS,build,providers,CORE,sha
import json,hashlib
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
REG=providers();LOG=Path('E:/ArkSimLogs/runs/chapter09_more_author_v1')
def module(key):return json.loads((OUT/(key+'.module.v1.json')).read_bytes())
def fixture(key):
 p=module(key)
 p['entities'].append({'id':'unit/more/guard','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':20000,'atk':1000,'def':137,'mres':23,'block_count':1}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'},'deployable':{'base_cost':1,'terrain':'ground','capacity':1,'cooldown_seconds':0},'abilities':['ability/more/silence','ability/more/unmute','ability/more/arts']}})
 p['buffs'].append({'id':'buff/more/silence','kind':'buff','selection_flags':{'abnormal_flags':[12]}})
 p['selectors'].append({'id':'selector/more/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]})
 for name,effect in [('silence',{'op':'apply_buff','buff':'buff/more/silence'}),('unmute',{'op':'remove_buff','buff':'buff/more/silence'}),('arts',{'op':'damage','damage_type':'arts','scale':1})]:
  p['abilities'].append({'id':'ability/more/'+name,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/more/enemy','timeline':[{'at':0,'effect':effect}]})
 p['scenarioDraft']={'id':'scene/more/'+key,'ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':5},'resources':{'dp':{'initial':10,'capacity':99}},'roster':['unit/more/guard'],'commands':[{'at':0,'action':'deploy','entity':'unit/more/guard','alias':'guard','row':0,'col':1}],'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'enemy','position':{'row':0,'col':1},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':4},'checkpoints':[]}}]}
 return p
def proof(p,name,split,end):
 pr=Compiler(providers=REG).compile(p);s=Engine.create(pr,providers=REG,seed=91620);s.advance(split)
 LOG.mkdir(parents=True,exist_ok=True);cp=LOG/(name+'.checkpoint.json');pin=write_ordered(cp,s.checkpoint());r=Engine.restore(pr,load_bound(cp,pin),providers=REG);s.advance(end-split);r.advance(end-split);head=replay(pr,s.export_replay(),providers=REG)
 assert s.checkpoint()==r.checkpoint()==head.checkpoint()
 assert list(s.session.events)==list(r.session.events)==list(head.session.events)
 out=ROOT/'validation/campaign/chapter09_more_author'/name;out.mkdir(parents=True,exist_ok=True)
 (out/'receipt.json').write_text(json.dumps({'runtime':CORE,'CP_and_head_equal':True,'events':len(s.session.events),'CP_sha':pin,'input_sha':hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),'log_cleanup_required':True,'whole_stage':False,'client_verified':False},indent=2))
 return s
@pytest.mark.parametrize('key',KEYS)
def test_actual_compile_rebuild_and_source_locks(key):
 p=module(key);assert p==build(key)
 assert all(sha(Path(k))==v for k,v in p['manifest']['metadata']['source_locks'].items())
@pytest.mark.parametrize('key,hit,cycle,amount',[('enemy_1170_dushld',15,120,563),('enemy_1169_duphlx',19,75,163)])
def test_melee_hit_duration_recovery_numeric(key,hit,cycle,amount):
 s=proof(fixture(key),key+'melee',hit-1,hit+cycle*2+1)
 hits=[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']
 assert hits[:3]==[(hit,amount),(hit+cycle,amount),(hit+cycle*2,amount)]
@pytest.mark.parametrize('key,normal',[('enemy_1170_dushld',300),('enemy_1169_duphlx',300),('enemy_1168_dumage',100)])
def test_silence_res_restoration_actual_damage(key,normal):
 p=fixture(key);p['scenarioDraft']['commands'] += [{'at':t,'action':'skill','source':'guard','ability':'ability/more/'+n} for t,n in [(2,'arts'),(4,'silence'),(6,'arts'),(8,'unmute'),(10,'arts')]]
 s=proof(p,key+'silence',5,12);hits=[e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted'];assert hits==pytest.approx([normal,1000 if normal==300 else 800,normal])
def mage_scene():
 p=fixture('enemy_1168_dumage');p['scenarioDraft']['commands']=[];p['scenarioDraft']['initialEntities'][0].pop('route');p['scenarioDraft']['initialEntities'][0]['position']['col']=0
 p['scenarioDraft']['initialEntities'].append({'definition':'unit/more/guard','instanceAlias':'guard','position':{'row':0,'col':2}})
 return p
def test_mage_arts300_RES23_launch19_travel6_full36_recovery90():
 p=mage_scene();s=proof(p,'mage_flight',20,120);hits=[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted'];assert hits==[(25,231),(115,231)]
@pytest.mark.parametrize('state,col',[({'side':0,'motion':2,'category':1,'unit_type':1},2),({'side':0,'motion':1,'category':1,'unit_type':1,'camouflage':True},2),({'side':0,'motion':1,'category':1,'unit_type':1,'target_free':True},2),({'side':0,'motion':1,'category':1,'unit_type':1},3)])
def test_mage_actual_qualification(state,col):
 p=mage_scene();p['entities'][1]['components']['selection_state']=state;p['scenarioDraft']['initialEntities'][1]['position']['col']=col
 s=proof(p,'mage_reject_'+hashlib.sha256(json.dumps([state,col]).encode()).hexdigest()[:12],20,50);assert not [e for e in s.session.events if e['type']=='damage.accepted']
def aura_scene():
 p=module('enemy_1169_duphlx');uid=p['entities'][0]['id']
 p['scenarioDraft']={'id':'scene/more/aura','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':5},'initialEntities':[{'definition':uid,'instanceAlias':name,'position':{'row':0,'col':col}} for name,col in [('a',0),('b',1),('c',2)]]}
 return p
def test_aura_source_radius1_excludes_self_adds_per_source200_and_retire():
 p=aura_scene();pr=Compiler(providers=REG).compile(p);s=Engine.create(pr,providers=REG);assert [s.ctx.attributes.value(x,'def') for x in ('a','b','c')]==[500,700,500]
 victim=deepcopy(p['entities'][0]);victim['id']='unit/more/retire_target';victim['tags'].append('retire_target');p['entities'].append(victim);p['scenarioDraft']['initialEntities'][1]['definition']=victim['id']
 p['selectors'].append({'id':'selector/more/retire_target','kind':'selector','region':{'type':'all'},'filters':[{'tag':'retire_target'}]})
 p['abilities'].append({'id':'ability/more/retire_target','kind':'ability','activation':{'mode':'manual'},'selector':'selector/more/retire_target','timeline':[{'at':0,'effect':{'op':'retire','parameters':{'reason':'withdrawn'}}}]})
 p['entities'][0]['components']['abilities'].append('ability/more/retire_target');p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'a','ability':'ability/more/retire_target'}]
 s=proof(p,'aura_retire',1,5);assert [s.ctx.attributes.value(x,'def') for x in ('a','c')]==[300,300]
@pytest.mark.parametrize('kind',['no_mask','neutral','player','category','free','fly'])
def test_aura_live_mask_side_category_free_qualifications(kind):
 p=aura_scene();e=deepcopy(p['entities'][0]);e['id']='unit/more/candidate';e['components']['buffs']['initial']=['buff/ch9/duphlx/mask'];e['components']['abilities']=[];e['components'].pop('behavior');st=e['components']['selection_state']
 if kind=='no_mask':e['components']['buffs']['initial']=[]
 if kind=='neutral':st['side']=2
 if kind=='player':st['side']=0
 if kind=='category':st['category']=2
 if kind=='free':st['target_free']=True
 if kind=='fly':st['motion']=2
 p['entities'].append(e);p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1]+[{'definition':e['id'],'instanceAlias':'candidate','position':{'row':0,'col':1}}]
 s=proof(p,'aura_'+kind,1,3);assert s.ctx.attributes.value('candidate','def')==(500 if kind=='fly' else 300)
def test_unsupported_coupled_closure_rejected():
 for key in ['enemy_1174_duholy','enemy_1175_dushdo']:
  with pytest.raises(ValueError,match='Unsupported source closure'):build(key)
