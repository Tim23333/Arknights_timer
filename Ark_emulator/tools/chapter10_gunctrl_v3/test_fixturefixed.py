"""Public source invincibility/output/allocation and NoSource author tests."""
import os,json,hashlib,traceback
from pathlib import Path
from copy import deepcopy
from tools.chapter10_gunctrl_v3.build import build,providers
from tools.chapter10_gunctrl_v1.build import BODY,P,bind_status_definitions,SOURCE,RANGE
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter10_gunctrl_v3';OUT.mkdir(parents=True,exist_ok=True);LOG=Path(os.environ['ARKSIM_RUN_DIR']);CORE=implementation_digest();assert CORE=='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18';REG=providers();RESULT=[];FACT={};ART=[]
def allocations(inputs,params,context):return {'accepted':True,'amount':23191,'allocations':[{'resource':'hp','amount':31711},{'resource':'hp','delta':-28717},{'resource':'sp','delta':11}],'events':[{'type':'peer.pipeline_marker','payload':{'target':inputs['target']['id']}}]}
REG['peer.cannon.allocations']={'callable':allocations,'version':'owned-public-hp-amount-delta-and-nonHP-event-v1'}
def fixture():
 p=build();actor={'id':'unit/peer/attacker','kind':'entity','tags':['probe'],'components':{'attributes':{'base':{'max_hp':23471,'atk':23191,'def':683,'mres':57,'block_count':5}},'resources':{'hp':{'role':'health','initial':23471,'capacity':23471}},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'spatial':{},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(actor);p['selectors'].append({'id':'selector/peer/cannon','kind':'selector','region':{'type':'all'},'filters':[{'tag':'gunctrl'},{'state':'alive'}],'limit':1})
 p['scenarioDraft']={'id':'scene/peer/cannon_v3','ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':10},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':BODY,'instanceAlias':'cannon','position':{'row':1,'col':1}},{'definition':actor['id'],'instanceAlias':'attacker','position':{'row':5,'col':6}}]};bind_status_definitions(p);return p

def cpp(p,label,end=13):
 def create():return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=2347123191)
 a=create();a.advance(end);b=create()
 for t in [4,8]:
  b.advance(t-b.session.time);f=LOG/(label+str(t)+'.checkpoint.json');h=write_ordered(f,b.checkpoint());ART.append({'path':str(f),'sha256':h,'bytes':f.stat().st_size});b=Engine.restore(b.program,load_bound(f,h),providers=REG)
 b.advance(end-b.session.time);h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();assert list(a.session.events)==list(b.session.events)==list(h.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==h.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==h.session.random.snapshot();return a

def incoming():
 p=fixture();commands=[]
 for i,kind in enumerate(['physical','arts','true']):
  aid='ability/peer/input/'+kind;p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/cannon','timeline':[{'at':0,'effect':{'op':'damage','damage_type':kind,'scale':1}}]});p['entities'][-1]['components']['abilities'].append(aid);commands.append({'at':2+i*3,'action':'skill','source':'attacker','ability':aid})
 p['scenarioDraft']['commands']=commands;s=cpp(p,'incoming');hp=s.ctx.resources.current('cannon','hp');hits=[thaw(e) for e in s.session.events if e['type']=='damage.accepted'];FACT['incoming']={'HP':hp,'hits':hits,'alive':s.ctx.alive('cannon'),'kills':s.ctx.state().get('kills'),'flags':s.ctx.spatial.selection_state('cannon',__import__('ark_sim.domains.selection',fromlist=['DEFAULT_STATE']).DEFAULT_STATE)['abnormal_flags']};assert hp==10000 and s.ctx.alive('cannon') and len(hits)==3 and all(e['payload']['amount']==0 for e in hits);assert s.ctx.state()['kills']==0

def allocated():
 p=fixture();p['rules'].append({'id':'rule/peer/allocations','kind':'rule','contract':'damage.pipeline','implementation':{'type':'provider','provider':'peer.cannon.allocations'}});aid='ability/peer/input/allocations';p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/cannon','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1,'rules':{'damage.pipeline':'rule/peer/allocations'}}}]});p['entities'][-1]['components']['abilities'].append(aid);p['scenarioDraft']['commands']=[{'at':5,'action':'skill','source':'attacker','ability':aid}];s=cpp(p,'allocated');hp=s.ctx.resources.current('cannon','hp');sp=s.ctx.resources.current('cannon','sp');events=[thaw(e) for e in s.session.events if e['type'] in ['peer.pipeline_marker','damage.accepted','resource.changed']];FACT['allocations']={'HP':hp,'SP':sp,'events':events};assert hp==10000 and sp>11 and any(e['type']=='peer.pipeline_marker' for e in events);assert next(e for e in events if e['type']=='damage.accepted')['payload']['amount']==0

def output():
 p=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':6,'effect':{'op':'modify_resource','target':2,'resource':'sp','value':120}}];s=cpp(p,'output');hp=s.ctx.resources.current('attacker','hp');hits=[thaw(e) for e in s.session.events if e['type']=='damage.accepted'];FACT['output']={'recipient_HP':hp,'cannon_HP':s.ctx.resources.current('cannon','hp'),'hits':hits};assert hp==20471 and s.ctx.resources.current('cannon','hp')==10000 and hits[0]['payload']['amount']==3000 and hits[0]['payload']['source']==2

def no_source_pipeline(inputs,params,context):
 return {'accepted':True,'amount':inputs['effect']['fixed_amount'],'allocations':[{'resource':'hp','amount':inputs['effect']['fixed_amount']}],'events':[]}
REG['peer.cannon.NoSource']={'callable':no_source_pipeline,'version':'source-absent-fixed-health-amount-v1'}
def no_source():
 p=fixture();p['rules'].append({'id':'rule/peer/NoSource','kind':'rule','contract':'damage.pipeline','implementation':{'type':'provider','provider':'peer.cannon.NoSource'}})
 def effect(modify,value):return {'op':'no_source_damage','target':2,'fixed_amount':value,'damage_type':'true','attack_type':'BUFF','damage_without_modify':modify,'ignore_for_sp':True,'node_is_env_damage':False,'env_blackboard_injected':False,'environmental':False,'origin':{'source':'independent-explicit-boundary'},'rules':{'damage.pipeline':'rule/peer/NoSource'}}
 p['scenarioDraft']['scheduledEffects']=[{'at':3,'effect':effect(False,15001)},{'at':7,'effect':effect(True,73)}];s=cpp(p,'nosource');hp=s.ctx.resources.current('cannon','hp');events=[thaw(e) for e in s.session.events if e['type'].startswith('damage.')];FACT['NoSource']={'HP':hp,'events':events,'native_boundary':'damage_without_modify=False receives hook; True bypasses it in existing kernel'};assert hp==9927 and s.ctx.alive('cannon');assert any(e['type']=='damage.modification_bypassed' for e in events)
 p['scenarioDraft']['scheduledEffects']=[{'at':3,'effect':effect(True,15001)}];s=cpp(p,'bypasszero');FACT['bypass_zeroHP']={'HP':s.ctx.resources.current('cannon','hp'),'alive':s.ctx.alive('cannon'),'nativeFlagsAfterDeath':thaw(s.ctx.buffs._instances('cannon'))};assert FACT['bypass_zeroHP']['HP']==0 and not FACT['bypass_zeroHP']['alive']

def guard():return {str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [SOURCE,RANGE,Path(__file__),ROOT/'tools/chapter10_gunctrl_v1/build.py',ROOT/'tools/chapter10_gunctrl_v2/build.py',ROOT/'tools/chapter10_gunctrl_v3/build.py']}
BEFORE=guard()
for name,fn in [('public_physical_arts_true_lethal_inputs_zero_CPP',incoming),('NoSource_modify_and_bypass_zeroHP_boundary_CPP',no_source)]:
 try:fn();RESULT.append({'case':name,'passed':True})
 except Exception:RESULT.append({'case':name,'passed':False,'traceback':traceback.format_exc()})
 after=guard();r={'core':CORE,'actual_exit':0 if all(e['passed'] for e in RESULT) and BEFORE==after else 1,'results':RESULT,'facts':FACT,'artifacts':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':BEFORE==after,'comparison_exclusions':[],'whole_stage':False};(OUT/'author.fixturefixed.v3.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'results':RESULT,'actual_exit':r['actual_exit']}));raise SystemExit(r['actual_exit'])
