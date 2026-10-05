"""Author numeric/ownership/CPP gate; raw only managed E runs."""
import os,json,traceback,hashlib
from pathlib import Path
from copy import deepcopy
from tools.chapter10_gunctrl_v1.build import *
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter10_gunctrl_v1';OUT.mkdir(parents=True,exist_ok=True);LOG=Path(os.environ['ARKSIM_RUN_DIR']);REG=providers();RESULT=[];FACT={};ART=[];CORE=implementation_digest()
def fixture(stage='level_main_10-14'):
 p=build(stage);p['buffs'] += [{'id':'buff/peer/noblock','kind':'buff','control':{'block':False}},{'id':'buff/peer/blockplus','kind':'buff','modifiers':[{'attribute':'block_count','layer':'flat','value':4}]}]
 initial=[{'definition':BODY,'instanceAlias':'cannon','position':{'row':0,'col':0}}]
 for name,block,pos,side in [('A',2,{'row':4,'col':4},0),('B',4,{'row':4,'col':5},0),('E',9,{'row':5,'col':4},1)]:
  entity='unit/peer/'+name;p['entities'].append({'id':entity,'kind':'entity','dependencies':['buff/peer/noblock','buff/peer/blockplus'],'tags':['player'] if side==0 else ['enemy'],'components':{'attributes':{'base':{'max_hp':17391,'atk':371,'def':853,'mres':63,'block_count':block}},'resources':{'hp':{'role':'health','initial':17391,'capacity':17391}},'selection_state':{'side':side,'category':1,'motion':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});initial.append({'definition':entity,'instanceAlias':name,'position':pos})
 p['scenarioDraft']={'id':'scene/peer/gunctrl','ruleset':'ruleset/ark_standard','map':{'rows':10,'cols':11},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':initial};bind_status_definitions(p);return p
def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=17391371)
def marks(s):return [a['id'] for a in s.session.world.entities() if any(b['definition']==MARK for b in a['components'].get('buffs',{}).get('instances',[]))]
def cpp(p,end,pins,label):
 a=create(p);a.advance(end);b=create(p)
 for t in pins:
  b.advance(t-b.session.time);f=LOG/(label+str(t)+'.checkpoint.json');h=write_ordered(f,b.checkpoint());ART.append({'path':str(f),'sha256':h,'bytes':f.stat().st_size});b=Engine.restore(b.program,load_bound(f,h),providers=REG)
 b.advance(end-b.session.time);h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();assert list(a.session.events)==list(b.session.events)==list(h.session.events);return a

def rank():
 s=create(fixture());s.advance(2);a=s.session.world.resolve('A');b=s.session.world.resolve('B');assert marks(s)==[b]
 s.ctx.buffs.apply('cannon',a,'buff/peer/blockplus');s.advance(1);assert marks(s)==[a]
 s.ctx.buffs.apply('cannon',a,'buff/peer/noblock');s.advance(1);assert marks(s)==[b]
 s.ctx.buffs.remove(a,'buff/peer/noblock');s.advance(1);assert marks(s)==[a]
 FACT['dynamic_rank']={'winner_B_then_A_then_B_then_A':True,'actual_NoBlock_applied_removed':True,'same_side_enemy_block9_not_selected':True}
def blast():
 p=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':5,'effect':{'op':'modify_resource','target':2,'resource':'sp','value':120}}];s=cpp(p,9,[4,6],'blast');a=s.session.world.resolve('A');b=s.session.world.resolve('B');e=s.session.world.resolve('E');c=s.session.world.resolve('cannon');hp={k:s.ctx.resources.current(k,'hp') for k in [a,b,e]};FACT['blast_probe']={'hp':hp,'sp':s.ctx.resources.current(c,'sp'),'events':[thaw(x) for x in s.session.events if x['type'] in ['ability.started','projectile.launched','projectile.reached','area.resolved','damage.accepted']]};assert set(hp.values())=={14391};assert any(x['type']=='ability.started' and x['payload']['ability']==SHOT for x in s.session.events);assert s.ctx.resources.current(c,'sp')<1
 FACT['blast']={'PURE3000_both_sides_DEF853_RES63_ignored':True,'actualSP120_payment':True,'CPP_head_all_fields_equal':True}
def retain():
 p=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':5,'effect':{'op':'modify_resource','target':2,'resource':'sp','value':120}},{'at':6,'effect':{'op':'retire','target':4,'parameters':{'reason':'withdraw'}}}];s=cpp(p,10,[5,7],'retained');hits=[thaw(x) for x in s.session.events if x['type']=='area.resolved'];FACT['retained_probe']={'areas':hits,'AHP':s.ctx.resources.current('A','hp'),'Bactive':s.ctx.active('B')};assert hits and hits[0]['payload']['center']=={'row':4,'col':5};assert s.ctx.resources.current('A','hp')==14391 and not s.ctx.active('B');FACT['retained_position_after_withdraw']=True

def passive():
 p=fixture();p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1];s=create(p);s.advance(3599);assert s.ctx.resources.current('cannon','sp')<120;assert not any(x['type']=='ability.started' for x in s.session.events);s.advance(2);FACT['passive']={'SP_at3601':s.ctx.resources.current('cannon','sp'),'starts':[thaw(x) for x in s.session.events if x['type']=='ability.started']};assert len(FACT['passive']['starts'])==1 and FACT['passive']['starts'][0]['time']==3600

def closure():
 p=fixture();p['buffs'].append({'id':'buff/peer/unmapped','kind':'buff','control':{'block':False}});p['entities'][1]['components']['buffs']={'initial':['buff/peer/unmapped']};before=None
 try:s=create(p)
 except Exception as e:assert 'status dependency missing' in str(e);FACT['missing_mapping_rejected']=str(e)
 else:raise AssertionError('unmapped actual Buff accepted')
 try:build('level_main_10-15',require_complete=True)
 except ValueError as e:assert 'required source-owned' in str(e)
 else:raise AssertionError('complete mixed-stage charge endpoint missing accepted')
 try:build('level_main_10-15',manfred_sp_binding={'unknown':'placeholder'})
 except ValueError:pass
 else:raise AssertionError('unimplemented supplied charge slot accepted')
 assert build('level_main_10-15')['manifest']['metadata']['native_predefine']['inst']['potentialRank']==1
 FACT['native_potential0_1_preserved_and_required_charge_slot_rejected']=True

def invalid():
 s=create(fixture());before=s.checkpoint()
 try:s.command({'action':'skill','source':'A','ability':SHOT})
 except Exception:pass
 else:raise AssertionError('foreign unowned cannon ability accepted')
 assert before==s.checkpoint();FACT['foreigncaller_atomic_reject']=True

def guard():return {str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in [SOURCE,RANGE,Path(__file__),Path(__file__).with_name('build.py')]}


def visuals():
 s=create(fixture());s.advance(2);target=s.session.world.resolve('B');one=next(b for b in s.ctx.buffs._instances(target) if b['definition']=='buff/'+P+'effect_2');s.advance(5);two=next(b for b in s.ctx.buffs._instances(target) if b['definition']=='buff/'+P+'effect_2');assert one['id']==two['id'] and one['generation']==two['generation'];s.ctx.buffs.apply('cannon','A','buff/peer/blockplus');s.advance(1);assert not any(b['definition'].startswith('buff/'+P+'effect_') for b in s.ctx.buffs._instances(target));FACT['derived_visual_idempotent_and_departure_cleanup']=True

def masks():
 p=fixture();original=deepcopy(p['entities'][1]);entries=[('free',0,1,1,{'target_free':True},(4,6)),('air',0,1,2,{},(3,5)),('corner',0,1,1,{},(6,7)),('device',0,4,1,{},(4,6)),('camo',0,1,1,{'camouflage':True},(4,6))]
 for name,side,category,motion,flags,pos in entries:
  e=deepcopy(original);e['id']='unit/peer/'+name;e['components']['selection_state']={'side':side,'category':category,'motion':motion,'unit_type':1,**flags};e['components']['attributes']['base']['block_count']=0;p['entities'].append(e);p['scenarioDraft']['initialEntities'].append({'definition':e['id'],'instanceAlias':name,'position':{'row':pos[0],'col':pos[1]}})
 p['scenarioDraft']['scheduledEffects']=[{'at':5,'effect':{'op':'modify_resource','target':2,'resource':'sp','value':120}}];bind_status_definitions(p);s=cpp(p,9,[4,6],'masks');hp={name:s.ctx.resources.current(name,'hp') for name,*rest in entries};FACT['live_native_masks']={'HP':hp,'area':[thaw(e) for e in s.session.events if e['type']=='area.resolved']};assert hp=={'free':14391,'air':14391,'corner':17391,'device':17391,'camo':17391}
BEFORE=guard()
try:masks();RESULT.append({'case':'native_area_cell_and_live_masks_CPP','passed':True})
except Exception:RESULT.append({'case':'native_area_cell_and_live_masks_CPP','passed':False,'traceback':traceback.format_exc()})
after=guard();r={'core':CORE,'actual_exit':0 if all(x['passed'] for x in RESULT) and after==BEFORE else 1,'results':RESULT,'facts':FACT,'artifacts':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':after==BEFORE,'whole_stage':False};(OUT/'author.masks.v1.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps({'results':RESULT,'actual_exit':r['actual_exit']}));raise SystemExit(r['actual_exit'])
