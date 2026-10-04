from copy import deepcopy
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from tools.chapter07_predefines.policies_v1 import providers as ore_registry
from tools.chapter07_strength_melee.policies_v1 import providers as strength_registry
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'packages/campaign'
ORE=BASE/'chapter07_predefines_consumer/ore.module.v3.json'
MINE=BASE/'chapter07_predefines_consumer/mine.module.v2.json'
STORY=BASE/'chapter07_predefines_consumer/story.controls.v2.json'
STRENGTH=[BASE/('chapter07_strength_melee/module.'+v+'.v6.json') for v in ['enemy_1083_sotiab','enemy_1083_sotiab_2','enemy_1078_sotisc']]
INPUTS=[];CAPTURES=[]
def registry():return {**ore_registry(),**strength_registry()}
def create(p,modules):
 INPUTS.append({'package':deepcopy(p),'modules':[str(x) for x in modules]});r=registry();return Engine.create(Compiler(providers=r).compile(p,packages=[str(x) for x in modules]),providers=r,seed=70761)
def package(k):return {'schemaVersion':2,'manifest':{'id':'package/peer/consumer/'+k,'requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/sp','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current+inputs.parameters.amount'}}],'buffs':[{'id':'buff/ch7/source/ore_immune','kind':'buff'},{'id':'buff/ch7/source/ore_listener','kind':'buff'}],'entities':[],'abilities':[],'behaviors':[{'id':'behavior/peer/modes','kind':'behavior','initial':'mode0','states':{'mode0':{},'mode1':{}}}],'scenarioDraft':{'id':'scene/peer/'+k,'ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':7},'objectives':{},'resources':{'dp':{'initial':100,'capacity':100},'deployment_capacity':{'initial':0,'capacity':0},'stock_ch7_mine':{'initial':15,'capacity':15}},'initialEntities':[]}}
def recipient(p,name,pos,selection=None):
 c={'attributes':{'base':{'max_hp':9000,'atk':17,'def':31,'mres':17}},'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'},'sp':{'initial':0,'capacity':20,'recovery_rule':'rule/peer/sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':1,**(selection or {})},'lifecycle':{'policy':'policy/ark_lifecycle'},'spatial':{},'behavior':{'machine':'behavior/peer/modes','state':'mode0'}}
 p['entities'].append({'id':'unit/peer/'+name,'kind':'entity','components':c});p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/'+name,'instanceAlias':name,'position':{'row':pos[0],'col':pos[1]}})
def controller(p,abilities):
 p['abilities']+=abilities;p['entities'].append({'id':'unit/peer/director','kind':'entity','components':{'abilities':[a['id'] for a in abilities],'spatial':{}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':0}})
def ability(k,effects):return {'id':'ability/peer/'+k,'kind':'ability','activation':{'mode':'manual','on_start':effects},'timeline':[]}
def command(s,k,t):s.submit({'action':'skill','source':'director','ability':'ability/peer/'+k},at=t)
def events(s,k):return [e for e in s.session.events if e['type']==k]
def capture(s,k):CAPTURES.append({'case':k,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'commands':s.export_replay()})
