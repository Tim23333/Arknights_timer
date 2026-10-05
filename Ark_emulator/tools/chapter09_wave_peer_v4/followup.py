"""Independent source typed patch and managed two-wave release, no author fixture."""
import os,sys,json,hashlib,traceback
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_finale_joint_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter09_stage919_assembly_v1.providers_v3 import providers
CORE='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18';assert implementation_digest()==CORE
BASE=ROOT/'packages/campaign/chapter09_stage_models';PARENT=BASE/'level_main_09-17.native_draft.v3.life99999.json';PACKAGE=BASE/'level_main_09-17.native_draft.v4.life99999.json';SOURCE=BASE/'level_main_09-17.mandra_next_wave.source.v4.json';OUT=ROOT/'validation/campaign/chapter09_wave_peer_v4';LOG=Path(os.environ['ARKSIM_RUN_DIR']);REG=providers();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();BODY='unit/ch9/mandra/body'
def exact(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 return a==b

def guard():
 assert implementation_digest()==CORE;assert sha(PACKAGE)=='2543569405d85808a2edc825cfa927b59a24a77b6aba92bb070efa0adea9ba92';files=[PARENT,PACKAGE,SOURCE,ROOT/'tools/chapter09_stage919_assembly_v1/providers_v3.py',ROOT/'tools/chapter09_stage919_wave_v4/patch.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts];return {str(p):sha(p) for p in files}
START=guard();OUT.mkdir(parents=True,exist_ok=True);RESULTS=[];FACTS={};ART=[];request={'op':'finish_timeline_wave','target':'source','parameters':{'finish_and_skip':False,'track_source_at_next_wave':False,'track_source_wave_delta':0,'track_all_managed_at_next_wave':False}}
def source_gate():
 parent=json.loads(PARENT.read_bytes());package=json.loads(PACKAGE.read_bytes());node=json.loads(SOURCE.read_bytes())['templates']['finish_current_wave_when_buff_finish']['parsed']['eventToActions']['ON_BUFF_FINISH'][0];assert exact({k:node[k] for k in ['_finishAndSkip','_trackSourceAtNextWave','_trackSourceAtWaveDelta','_trackAllManagedEnemiesAtNextWave','_sourceType']},{'_finishAndSkip':False,'_trackSourceAtNextWave':False,'_trackSourceAtWaveDelta':0,'_trackAllManagedEnemiesAtNextWave':False,'_sourceType':'BUFF_OWNER'});boss=next(d for d in package['definitions'] if d['id']==BODY);assert exact(boss['components']['rebirth']['on_finish'][-1],request);boss['components']['rebirth']['on_finish'].pop();assert exact(package,parent);FACTS['source']={'typedflags_exact':True,'single_on_finish_append_only':True,'native63_action_route_HP_LP2_unchanged':True}

def scene():
 p=json.loads(PACKAGE.read_bytes());defs={d['id']:d for d in p['definitions']};keeper=next(k for k in defs if k.startswith('unit/ch9/duhond/'));p['definitions'] += [{'id':'unit/peer/wave/killer','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':41173,'atk':137000,'def':991,'mres':53}},'resources':{'hp':{'role':'health','initial':41173,'capacity':41173}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'abilities':['ability/peer/wave/kill'],'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':'selector/peer/wave/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}],'limit':1},{'id':'ability/peer/wave/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/wave/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}]
 def spawn(definition,alias,pos):return {'kind':'spawn','spawn':{'definition':definition,'instanceAlias':alias,'position':pos},'count':1,'delay_seconds':0.0,'interval_seconds':1.0,'managed':True,'blocks_wave':True,'blocks_fragment':False}
 future=spawn(keeper,'future',{'row':1,'col':10});future['delay_seconds']=8.0;p['scenarioDraft']={'id':'scene/peer/wave/independent','ruleset':'ruleset/ark_standard','map':{'rows':11,'cols':12},'resources':{'life':{'initial':99999,'capacity':99999}},'rules':deepcopy(p['scenarioDraft']['rules']),'initialEntities':[{'definition':'unit/peer/wave/killer','instanceAlias':'killer','position':{'row':8,'col':7}}],'commands':[{'at':11,'action':'skill','source':'killer','ability':'ability/peer/wave/kill'}],'objectives':{'type':'waves','life_resource':'life'},'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':0.0,'post_delay_seconds':0.0,'max_wait_seconds':-1.0,'fragments':[{'pre_delay_seconds':0.0,'actions':[spawn(BODY,'boss',{'row':4,'col':4}),spawn(keeper,'keeper',{'row':9,'col':10})]}]},{'pre_delay_seconds':0.0,'post_delay_seconds':0.0,'max_wait_seconds':-1.0,'fragments':[{'pre_delay_seconds':5.0,'actions':[future]}]}]}};return p

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=41173991)
def actual_gate():
 p=scene();a=create(p);a.advance(560);b=create(p);pins=[]
 for tick in [155,164,553]:
  b.advance(tick-b.session.time);path=LOG/('wave_'+str(tick)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append({'path':str(path),'sha256':pin,'bytes':path.stat().st_size});b=Engine.restore(b.program,load_bound(path,pin),providers=REG)
 b.advance(560-b.session.time);h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();assert list(a.session.events)==list(b.session.events)==list(h.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==h.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==h.session.random.snapshot();ART.extend(pins);timeline=a.ctx.state()['timeline'];boss=a.session.world.resolve('boss');keeper=a.session.world.resolve('keeper');req=timeline['finish_requests']['0'];assert req['source']==boss and req['requested_at']==161 and exact(req['parameters'],request['parameters']);assert a.ctx.alive(boss) and a.ctx.alive(keeper);assert a.ctx.resources.current(boss,'hp')==50000 and a.ctx.resources.current(keeper,'hp')==2800;assert timeline['members'][str(boss)]['wave']==timeline['members'][str(keeper)]['wave']==0;born=[thaw(e) for e in a.session.events if e['type']=='timeline.action' and e['payload'].get('wave')==1 and e['payload'].get('kind')=='spawn'];FACTS['timing_probe']={'timeline_actions':born,'timeline_origins':thaw(timeline.get('origins',{})),'finish_request':thaw(req)};assert len(born)==1 and born[0]['time']==req['requested_at']+390==551;assert a.ctx.state()['kills']==a.ctx.state()['leaks']==0;assert a.ctx.state()['pending_waves']==0;assert not a.ctx.state()['finished'];FACTS['actual']={'public_lethal_tick':11,'real_rebirth_finish':161,'wave1_birth':551,'wave1_fragment_pre5s_spawn_pre8s':True,'boss_HP50000_keeperHP2800_alive':True,'all_tracking_flags_false_no_transfer':True,'kills0_leaks0':True,'input_births3_actual_births3':True,'pending_wave_births0_no_clamping':True,'complete_CPP_head_equal':True}

try:
 actual_gate();RESULTS.append({'case':'managedactual_two_wave_CPPhead_correct_timing','passed':True})
except Exception as e:RESULTS.append({'case':'managedactual_two_wave_CPPhead_correct_timing','passed':False,'error':str(e),'traceback':traceback.format_exc()})
now=guard();r={'core':CORE,'actual_exit':0 if all(x['passed'] for x in RESULTS) and now==START else 1,'results':RESULTS,'facts':FACTS,'source_before':START,'source_after':now,'source_guard_equal':now==START,'artifacts':ART,'comparison_exclusions':[],'whole_stage':False};(OUT/'actual.correct.v4.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps({'actual_exit':r['actual_exit'],'results':RESULTS}));raise SystemExit(r['actual_exit'])
