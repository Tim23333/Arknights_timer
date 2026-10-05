"""Fresh independent native area/mask and INVINCIBLE damage counter."""
import os,json,hashlib,traceback
from pathlib import Path
from copy import deepcopy
from tools.chapter10_gunctrl_v2.build import build,providers
from tools.chapter10_gunctrl_v1.build import BODY,SHOT,MARK,P,bind_status_definitions,SOURCE,RANGE
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter10_gunctrl_independent_v2';OUT.mkdir(parents=True,exist_ok=True);LOG=Path(os.environ['ARKSIM_RUN_DIR']);REG=providers();CORE=implementation_digest();assert CORE=='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18';RESULT=[];FACT={};ART=[]
def fixture():
 p=build();initial=[{'definition':BODY,'instanceAlias':'cannon','position':{'row':1,'col':1}}];specs=[('focus',0,1,1,[],(5,6),9),('enemy',1,1,1,[],(5,7),0),('allyfree_enemy',1,1,1,[15],(6,6),0),('allyfree_player',0,1,1,[15],(4,6),0),('free_player',0,1,1,[2],(5,5),0),('invisible',0,1,1,[9],(4,5),0),('camo',0,1,1,[17],(4,7),0),('air',0,1,2,[],(3,6),0),('corner',0,1,1,[],(7,8),0),('device',0,4,1,[],(6,5),0),('neutral',2,1,1,[],(6,7),0)]
 for name,side,category,motion,flags,pos,block in specs:
  eid='unit/independent/'+name;buff='buff/independent/'+name;p['buffs'].append({'id':buff,'kind':'buff','selection_flags':{'abnormal_flags':flags}});p['entities'].append({'id':eid,'kind':'entity','tags':['probe'],'components':{'attributes':{'base':{'max_hp':23327,'atk':971,'def':671,'mres':57,'block_count':block}},'resources':{'hp':{'role':'health','initial':23327,'capacity':23327}},'selection_state':{'side':side,'category':category,'motion':motion,'unit_type':1},'spatial':{},'buffs':{'initial':[buff]},'lifecycle':{'policy':'policy/ark_lifecycle'}}});initial.append({'definition':eid,'instanceAlias':name,'position':{'row':pos[0],'col':pos[1]}})
 p['scenarioDraft']={'id':'scene/independent/gunctrl_v2','ruleset':'ruleset/ark_standard','map':{'rows':10,'cols':12},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':initial};bind_status_definitions(p);return p,[x[0] for x in specs]
def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=23327971)
def cpp(p,label):
 a=create(p);a.advance(11);b=create(p)
 for t in [5,8]:
  b.advance(t-b.session.time);f=LOG/(label+str(t)+'.checkpoint.json');h=write_ordered(f,b.checkpoint());ART.append({'path':str(f),'sha256':h,'bytes':f.stat().st_size});b=Engine.restore(b.program,load_bound(f,h),providers=REG)
 b.advance(11-b.session.time);h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();assert list(a.session.events)==list(b.session.events)==list(h.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==h.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==h.session.random.snapshot();return a

def area():
 p,names=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':6,'effect':{'op':'modify_resource','target':2,'resource':'sp','value':120}}];s=cpp(p,'area');hp={name:s.ctx.resources.current(name,'hp') for name in names};states={name:s.ctx.spatial.selection_state(name,DEFAULT_STATE) for name in names};FACT['area']={'HP':hp,'actual_projected_states':states,'events':[thaw(e) for e in s.session.events if e['type'] in ['area.resolved','damage.accepted','projectile.launched']]};hit={'focus','enemy','allyfree_player','free_player','air'};assert hp=={name:20327 if name in hit else 23327 for name in names};assert states['allyfree_enemy']['ally_target_free'] and states['free_player']['target_free'] and states['invisible']['invisible'] and states['camo']['camouflage'];FACT['native_area21_complete_qualified_masks_CPP']=True

def retired():
 p,names=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':6,'effect':{'op':'modify_resource','target':2,'resource':'sp','value':120}},{'at':7,'effect':{'op':'retire','target':3,'parameters':{'reason':'withdraw'}}}];s=cpp(p,'retired');areas=[thaw(e) for e in s.session.events if e['type']=='area.resolved'];FACT['retained']={'areas':areas,'focusactive':s.ctx.active('focus'),'enemyHP':s.ctx.resources.current('enemy','hp'),'allyfreeEnemyHP':s.ctx.resources.current('allyfree_enemy','hp')};assert areas[0]['payload']['center']=={'row':5,'col':6} and not s.ctx.active('focus');assert s.ctx.resources.current('enemy','hp')==20327 and s.ctx.resources.current('allyfree_enemy','hp')==23327;FACT['impact_current_masks_at_retained_capture_CPP']=True

def invincible():
 p,names=fixture();selector='selector/independent/cannon';ability='ability/independent/body_damage';p['selectors'].append({'id':selector,'kind':'selector','region':{'type':'all'},'filters':[{'tag':'gunctrl'},{'state':'alive'}],'limit':1});p['abilities'].append({'id':ability,'kind':'ability','activation':{'mode':'manual'},'selector':selector,'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical','scale':1}}]});p['entities'][1]['components']['abilities']=[ability];p['scenarioDraft']['commands']=[{'at':6,'action':'skill','source':'focus','ability':ability}];s=cpp(p,'immune');state=s.ctx.spatial.selection_state('cannon',DEFAULT_STATE);hp=s.ctx.resources.current('cannon','hp');events=[thaw(e) for e in s.session.events if e['type'] in ['ability.started','damage.accepted']];FACT['invincible_counter']={'native_flag_name':'AbnormalFlag.INVINCIBLE=5; HEAL_FREE=7, dump declaration','actual_flags':state['abnormal_flags'],'native_buff_instances':thaw(s.ctx.buffs._instances('cannon')),'native_expected_HP':10000,'actual_HP':hp,'actual_damage_events':events,'public_owned_cast':True,'complete_CPP_head_equal':True};(OUT/'counter.invincible.actual.v2.json').write_text(json.dumps({'core':CORE,'facts':FACT['invincible_counter'],'counter':hp!=10000,'scope':'Native cannon source INVINCIBLE5 not enforced by current content damage; no whole stage claim'},indent=2),encoding='utf8');assert 5 in state['abnormal_flags'] and 7 in state['abnormal_flags'];assert hp==10000,'native INVINCIBLE5 projected but public physical damage reduced cannon HP to '+str(hp)

def guard():
 files=[SOURCE,RANGE,Path(__file__),ROOT/'tools/chapter10_gunctrl_v1/build.py',ROOT/'tools/chapter10_gunctrl_v2/build.py',ROOT/'validation/campaign/chapter10_gunctrl_peer_v1/freeze.v2.json']+list((ROOT/'packages/campaign/chapter10_consumers/gunctrl_v2').glob('*.json'))+[x for x in (ROOT/'ark_sim').rglob('*') if x.is_file() and x.suffix in ['.py','.json'] and 'validation' not in x.parts]
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
BEFORE=guard()
for name,fn in [('fresh_retired_captured_position_CPP',retired),('native_device_INVINCIBLE_damage_CPP',invincible)]:
 try:fn();RESULT.append({'case':name,'passed':True})
 except Exception:RESULT.append({'case':name,'passed':False,'traceback':traceback.format_exc()})
 after=guard();r={'core':CORE,'actual_exit':0 if all(x['passed'] for x in RESULT) and BEFORE==after else 1,'results':RESULT,'facts':FACT,'artifacts':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':BEFORE==after,'comparison_exclusions':[],'whole_stage':False};(OUT/'peer.remaining.actual.v2.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'results':RESULT,'actual_exit':r['actual_exit']}));raise SystemExit(r['actual_exit'])
