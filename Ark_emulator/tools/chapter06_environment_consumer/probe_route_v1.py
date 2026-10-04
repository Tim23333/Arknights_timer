"""Unshortened native portal route on real existing source snsbr, bounded disk CP/head."""
import hashlib,json,sys,time
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';OUT=Path('E:/ArkSimEvidence/chapter06_environment_v1');sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import observations,write_checkpoint,load_checkpoint
CORE='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a';MODULE=ROOT/'packages/campaign/chapter06_environment_consumer/module.reference.json';UNIT=ROOT/'packages/campaign/chapter06_units/melee_v2/model.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 assert implementation_digest()==CORE;OUT.mkdir(parents=True,exist_ok=True);source=json.loads(MODULE.read_bytes());stage=source['manifest']['metadata']['native_stages']['level_main_06-14'];p=json.loads(UNIT.read_bytes());uid=next(e['id'] for e in p['entities'] if '/enemy_1064_snsbr/' in e['id']);route=stage['converted_used_routes']['1'];p['scenarioDraft']={'id':'scene/ch6/environment/full_native_route1','ruleset':'ruleset/ark_standard','seed':616,'map':stage['converted_map'],'objectives':{},'rules':{'movement.path':'rule/m7_diagonal_path','movement.speed':'rule/ch6/env/native_move_multiplier'},'initialEntities':[{'definition':uid,'instanceAlias':'source_mover','route':route,'position':route['startPosition']}],'metadata':{'source_route_actor_policy':'Exact source snsbr HP3400/ATK360/DEF100/speed1.1 runs untouched native boss-route1 to isolate environment geometry; not Boss skill/lifecycle acceptance','native_route_actor_original':'enemy_1510_frstar2','native_route_index':1,'native_route':stage['native_routes'][1]}}
 p['rules'].append({'id':'rule/ch6/env/native_move_multiplier','kind':'rule','contract':'movement.speed','implementation':{'type':'expression','expression':'inputs.attributes.move_speed * 0.5'}});inputs=OUT/'input.json';active=OUT/'original.active.jsonl';assert not inputs.exists() and not active.exists();inputs.write_text(json.dumps(p,indent=2)+'\n',encoding='utf8',newline='');paths=list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))+[MODULE,UNIT,Path(__file__),ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py',ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v13.py',ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v12.py',inputs];before={str(x):sha(x) for x in paths if x.exists()};program=Compiler().compile(p);s=Engine.create(program,event_journal_path=active);cp=None;started=time.monotonic()
 while s.session.time<18000:
  s.session.advance(100);entity=s.ctx.entity('source_mover');position=entity['components']['spatial']['position'];runtime=entity['components']['runtime'];print(json.dumps({'tick':s.session.time,'position':dict(position),'alive':runtime['alive'],'state':runtime['state']}),flush=True)
  if cp is None and s.session.time==500:cp=write_checkpoint(s,OUT/'actual500.cp.json');load_checkpoint(cp)
  if not runtime['alive']:break
 assert cp is not None and not s.ctx.alive('source_mover');end=s.session.time;original=observations(s,OUT/'original.events.jsonl');record=s.export_replay();(OUT/'replay.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8',newline='');del s
 r=Engine.restore(program,load_checkpoint(cp));r.session.advance(end-r.session.time);continued=observations(r,OUT/'continued.events.jsonl');del r;h=replay(program,record,event_journal_path=OUT/'head.active.jsonl');head=observations(h,OUT/'head.events.jsonl');del h;fields=('snapshot','events','event_count','continuation_state');assert all(original[k]==continued[k]==head[k] for k in fields);visibility=[];positions=[]
 with Path(original['export']['path']).open() as f:
  for line in f:
   e=json.loads(line)
   if e['type']=='movement.visibility_changed':visibility.append(e)
   if e['type'].startswith('movement.') and len(positions)<100:positions.append(e)
 assert len(visibility)==6;after={str(x):sha(x) for x in paths if x.exists()};assert before==after and implementation_digest()==CORE;result={'passed':True,'core':CORE,'source_before':before,'source_after':after,'module_sha':sha(MODULE),'source_unit_sha':sha(UNIT),'complete_native_route1_used':True,'native_waits_and_offsets_unchanged':True,'actor_exact_sourceHP3400_retained':True,'actor_is_source_snsbr_not_Boss':True,'end_tick':end,'checkpoint':cp,'CP_resume_equal':True,'public_head_equal':True,'observations':{'original':original,'continued':continued,'head':head},'actual_portal_visibility_events':visibility,'movement_samples':positions,'elapsed':time.monotonic()-started,'Boss_acceptance':False,'whole_stage_executed':False,'client_verified':False};out=OUT/'verification.json';out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'passed':True,'events':original['event_count'],'visibility':len(visibility),'sha':sha(out)}))
if __name__=='__main__':main()
