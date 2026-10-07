"""Pause-only read-only dependency inventory; does not import simulator."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];GIT=ROOT.parent;OUT=ROOT/'validation/campaign/chapter10_dmech_source_peer_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
scope=re.compile(r'(^|[/\\])chapter(?:0(?:9)?|10|11|12|13|14|15|16|17)(?:[_/\\]|$)')
selected=[]
for base in [ROOT/'packages/campaign',ROOT/'scenarios/campaign']:
 if base.exists():selected.extend(p for p in base.rglob('*.json') if scope.search(str(p.relative_to(base))))
external={};missing={};errors=[];references=0
def walk(v,owner):
 global references
 if isinstance(v,dict):
  locks=v.get('source_locks')
  if isinstance(locks,dict):
   for path,pin in locks.items():
    if not isinstance(path,str):continue
    references+=1;p=Path(path)
    if not p.is_absolute():
     candidates=[GIT/p,ROOT/p];p=next((x for x in candidates if x.exists()),candidates[0])
    p=p.resolve()
    if not p.exists():missing.setdefault(str(p),[]).append(str(owner));continue
    if not p.is_relative_to(GIT):
     entry=external.setdefault(str(p),{'type':'file' if p.is_file() else 'directory','suffix':p.suffix,'bytes':p.stat().st_size if p.is_file() else None,'pins':[],'referenced_by':[]})
     if pin not in entry['pins']:entry['pins'].append(pin)
     if str(owner) not in entry['referenced_by']:entry['referenced_by'].append(str(owner))
  for x in v.values():walk(x,owner)
 elif isinstance(v,list):
  for x in v:walk(x,owner)
for p in selected:
 try:walk(json.loads(p.read_bytes()),p)
 except Exception as e:errors.append({'path':str(p),'error':str(e)})
receipts=[OUT/'final.freeze.v1.json',OUT/'actual.v3.json',OUT/'frozen_recipient.actual.v1.json',ROOT/'validation/campaign/campaign_owned_dead_callback_peer_v1/final.freeze.v1.json',ROOT/'validation/campaign/chapter0_stage_input_peer_v1/final.freeze.v1.json',ROOT/'validation/campaign/chapter0_stage_input_peer_v1/plan.review.v5.json']
report={'schema':'ark-sim/paused-peer-closeout/v1','paused':True,'no_new_simulation_or_business_validation':True,'completed':[{'path':str(p),'sha256':sha(p)} for p in receipts],'remaining':['Dmech source/client method-body equivalence and whole stage are unapproved; independent bounded source peer is complete.','Source0 input/plan static review complete; actual full-plan/whole/UI pause and render timing remain separate Root gates.','No further callback/source development authorized while paused.'],'own_live_python_processes':[],'process_check':'Read-only CIM scan matched chapter10_dmech_source_peer_v1, campaign_owned_dead_callback_peer_v1, chapter0_stage_input_peer_v1 Python command lines; no matches.','git_root':str(GIT),'dependency_scan_scope':'JSON inputs under packages/campaign and scenarios/campaign directories matching chapters0,09,10,11–17. Recursively reads explicit source_locks keys only; not a complete dependency or dynamic import closure.','scanned_JSON_count':len(selected),'source_lock_references':references,'outside_git_root':external,'missing_references':missing,'parse_errors':errors,'migration_recommendations':['Copy each actual external source file byte-for-byte to a dedicated offline source archive, preserve original SHA pins and original-path provenance; update paths only through new versioned source inputs after resume.','Do not edit frozen source_locks in place or relabel prior runtime evidence. Preserve separately any ignored unpack_work/data dependencies inside Git root; this outside-root scan does not certify Git tracking.','Keep E ArkSimLogs receipts as compact historical proof; deleted raw logs cannot be reread as fresh evidence. Active Root runs must be stopped/cleaned only by Root under the pause closeout.']}
p=OUT/'paused.handoff.v1.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'handoff_sha':sha(p),'scanned':len(selected),'outside':len(external),'outside_bytes':sum(x['bytes'] or 0 for x in external.values()),'missing':len(missing),'parse_errors':len(errors)}))
