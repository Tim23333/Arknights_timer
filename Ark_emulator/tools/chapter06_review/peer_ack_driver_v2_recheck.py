import sys,json,hashlib,traceback,base64,re
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter06_review/ack_driver_v2_recheck_final';OUT.mkdir(exist_ok=False)
SOURCE=ROOT/'packages/campaign/chapter06_predefines/source.reference.json';HELPER=ROOT/'tools/control_driver/public_ack_v2.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
 with p.open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
FILES=[SOURCE,HELPER,Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',OUT.parent/'ack_driver_peer_v2/forward_skip.json']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
def guard():return {str(p):sha(p) for p in sorted(set(FILES))}
BEFORE=guard();controls=[];fragments=[];source=json.loads(SOURCE.read_bytes());expected_rows=[]
for i,(key,story) in enumerate(source['stories'].items()):
 payload=base64.b64decode(story['payload_base64']);assert hashlib.sha256(payload).hexdigest()==story['payload_sha256'];steps=[]
 for line,text in enumerate(payload.decode('utf8').splitlines(),1):
  if not text.strip():continue
  m=re.fullmatch(r'\[([A-Za-z_]+)(?:\((.*?)\))?\]\s*(.*)',text);assert m
  row={'source_story_key':key,'source_line':line,'raw_utf8':text};expected_rows.append(row)
  steps.append({'kind':'effects','effects':[{'op':'emit','target':'battle','event':'peer.source_story.row','payload':row}]})
  if m[1]=='PopupDialog':steps.append({'kind':'ack','key':key+'/line/'+str(line)})
 lock={'op':'input_lock','target':'battle','parameters':{'key':key,'enabled':True}};unlock=deepcopy(lock);unlock['parameters']['enabled']=False
 ident='control/peer/story/'+str(i);controls.append({'id':ident,'kind':'control','clock_policy':'logical','ack_policy':'external','steps':steps,'on_start':[lock],'on_complete':[unlock],'on_cancel':[deepcopy(unlock)]})
 fragments.append({'actions':[{'kind':'control','definition':ident,'instanceAlias':'story/'+str(i),'managed':True,'blocks_wave':True,'blocks_fragment':True}]})
p={'schemaVersion':2,'manifest':{'id':'package/peer/ack_source_chain','requires':['preset/ark_standard']},'controls':controls,'scenarioDraft':{'id':'scene/peer/ack_source_chain','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'resources':{},'objectives':{},'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':fragments}]}}};write(OUT/'input.json',p)
s=Engine.create(Compiler().compile(p),seed=6121);driver=PublicAckDriver(s);driver.advance_to(1)
write(OUT/'restore_state_initial.json',driver.checkpoint());cp=OUT/'ordered.bundle.json';h=write_ordered(cp,{'simulation':s.checkpoint(),'driver':driver.checkpoint()});loaded=load_bound(cp,h)
r=Engine.restore(s.program,loaded['simulation']);d=PublicAckDriver(r,loaded['driver']);driver.advance_to(30);d.advance_to(30);rep=replay(s.program,s.export_replay())
results=[]
try:
 assert s.checkpoint()==r.checkpoint()==rep.checkpoint() and driver.checkpoint()==d.checkpoint()
 assert s.snapshot()==r.snapshot()==rep.snapshot() and thaw(tuple(s.session.events))==thaw(tuple(rep.session.events))
 assert [thaw(e['payload']) for e in s.session.events if e['type']=='peer.source_story.row']==[{**row,'source':s.session.world.resolve('system/battle'),'target':s.session.world.resolve('system/battle')} for row in expected_rows]
 assert len(driver.submitted)==7 and len([e for e in s.session.events if e['type']=='control.completed'])==5
 assert not s.ctx.state()['input_locks'] and not [e for e in s.session.events if e['type']=='command.rejected']
 old=driver.checkpoint();driver.observe();assert old==driver.checkpoint()
 results.append({'case':'five_actual_source_story_chain_restore_replay_and_repeat_observe','passed':True})
except Exception:results.append({'case':'five_actual_source_story_chain_restore_replay_and_repeat_observe','passed':False,'error':traceback.format_exc()})
for label in ['forged_event_id','duplicate_ledger_entry','rewind_cursor','missing_consumed_ledger','float_clock','bool_clock','bool_submission_clock']:
 state=deepcopy(loaded['driver'])
 if label=='forged_event_id':state['submitted'][0]['event']=999999
 elif label=='duplicate_ledger_entry':state['submitted'].append(deepcopy(state['submitted'][0]))
 elif label=='rewind_cursor':state['cursor']=0
 elif label=='missing_consumed_ledger':state['submitted']=[]
 elif label=='float_clock':state['at']=1.0
 elif label=='bool_clock':state['at']=True
 elif label=='bool_submission_clock':state['submitted'][0]['submitted_at']=True
 restored=Engine.restore(s.program,loaded['simulation']);caught=None
 try:bad=PublicAckDriver(restored,state)
 except (ValueError,KeyError,TypeError) as error:caught=str(error)
 result={'case':label,'passed':caught is not None,'expected':'Reject invalid state before resuming','actual':'rejected' if caught else 'accepted','reason':caught,'state':state}
 if caught is None and label in ['missing_consumed_ledger','forged_event_id']:
  try:bad.advance_to(10);result['continuation_commands']=restored.export_replay();result['continuation_events']=thaw(tuple(restored.session.events))
  except Exception:result['continuation_error']=traceback.format_exc()
 write(OUT/(label+'.json'),result);results.append({k:v for k,v in result.items() if k not in ['state','continuation_events','continuation_commands']})
fresh=Engine.create(s.program,seed=6121);fresh.advance(1)
state=json.loads((OUT.parent/'ack_driver_peer_v2/forward_skip.json').read_text(encoding='utf8'))['forged_state'];assert state['cursor']==len(fresh.session.events)
try:
 skipped=PublicAckDriver(fresh,state)
except (ValueError,KeyError,TypeError) as error:
 outcome={'case':'forward_cursor_skips_unsubmitted_real_wait','passed':True,'actual':'rejected','reason':str(error)}
else:
 skipped.advance_to(30)
 outcome={'case':'forward_cursor_skips_unsubmitted_real_wait','passed':False,'actual':'accepted','ack_commands':fresh.export_replay()['commands'],'completed_controls':len([e for e in fresh.session.events if e['type']=='control.completed']),'controls':fresh.ctx.state().get('controls'),'events':thaw(tuple(fresh.session.events)),'forged_state':state}
write(OUT/'forward_skip.json',outcome);results.append({k:v for k,v in outcome.items() if k not in ['controls','events','forged_state']})
write(OUT/'actual_chain_capture.json',{'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'driver':driver.checkpoint(),'disk_sha':h})
AFTER=guard();report={'core':implementation_digest(),'helper_sha':sha(HELPER),'results':results,'guards_before':BEFORE,'guards_after':AFTER,'guards_equal':BEFORE==AFTER,'scope':'Independent source five-story7dialogue external-control chain and driver restoration validation, noNPC/enemy/specialspawn/fullstage execution. Failurestates from corrupted/tampered checkpoint host input, unchanged source/kernel.'}
write(OUT/'verification.json',report);print(json.dumps({'results':results,'sha':sha(OUT/'verification.json'),'guards_equal':BEFORE==AFTER},ensure_ascii=False))
