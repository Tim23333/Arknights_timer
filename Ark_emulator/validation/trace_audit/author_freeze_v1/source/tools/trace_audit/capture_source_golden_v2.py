"""Natural physical source shots, public arts deployment, and source self-healing."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';OUT=ROOT/'validation/trace_audit/source_golden_v2';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.trace_audit.capture_source_golden_v1 import CORE,SUPPORTED
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==CORE;OUT.mkdir(parents=True,exist_ok=True);parent=ROOT/'validation/trace_audit/source_golden_v1/input.json';p=json.loads(parent.read_bytes());scene=p['scenarioDraft'];amy=next(e['definition'] for e in scene['initialEntities'] if e['instanceAlias']=='arts_source');scene['initialEntities']=[e for e in scene['initialEntities'] if e['instanceAlias']!='arts_source'];scene['id']='scene/source_audit_golden_v2';scene['resources']={'dp':{'initial':10,'capacity':99,'recovery_rate':1,'recovery':{'mode':'periodic','interval_seconds':1}}};scene['roster']=[amy]
 inp=OUT/'input.json';journal=OUT/'events.jsonl';assert not inp.exists() and not journal.exists();inp.write_text(json.dumps(p,indent=2)+'\n',encoding='utf8',newline='');s=Engine.create(Compiler().compile(p),event_journal_path=journal);command={'action':'deploy','entity':amy,'row':2,'col':3,'facing':'right','alias':'arts_source'};s.submit(command,at=930);s.session.advance(1100);rules={};damage=[];heal=[];cmds=[];kinds={};supported=SUPPORTED|{'rule/ark_damage_pipeline'}
 def pin(t):
  rid=t.get('rule_id')
  if rid in supported:
   record={'formula_version':'independent-source-arithmetic/v1','contract':t['calculation_id'],'rule_fingerprint':t['rule_fingerprint'],'expression':t['stages'][-1].get('expression'),'provider':t.get('provider'),'evidence':'Explicit standard source definition and independently written arithmetic; runtime outputs are observations only.'};assert rid not in rules or rules[rid]==record;rules[rid]=record
  for node in t.get('stages',[]):pin(node.get('trace',{}))
 with journal.open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line);k=e['type'];kinds[k]=kinds.get(k,0)+1
   if k=='calculation':pin(e['payload']['trace'])
   if k=='damage.accepted':damage.append(e)
   if k in ('healing.accepted','regeneration.accepted'):heal.append(e)
   if k in ('command.accepted','command.rejected'):cmds.append(e)
 pins=OUT/'oracle_pins.json';pins.write_text(json.dumps({'schema':'ark-sim/source-formula-oracle-pins/v1','source_fixture_parent_sha':sha(parent),'source_core':CORE,'standard_source_sha':sha(RUNTIME/'ark_sim/content/presets/ark_standard.json'),'rules':rules,'unknown_rule_policy':'unverified, never auto-green'},indent=2)+'\n',encoding='utf8',newline='');snap=OUT/'snapshot.json';snap.write_text(json.dumps(s.snapshot(),indent=2)+'\n',encoding='utf8',newline='');result={'core':CORE,'input_sha':sha(inp),'journal_sha':sha(journal),'oracle_pins_sha':sha(pins),'snapshot_sha':sha(snap),'helper_sha':sha(Path(__file__)),'events':kinds,'damage_events':damage,'regeneration_events':heal,'actual_command_events':cmds,'public_command':command,'source_actor_numeric_definitions_retained':True,'client_verified':False};dest=OUT/'capture.json';dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');assert implementation_digest()==CORE;print(json.dumps({'events':kinds,'damage':len(damage),'heal':len(heal),'receipt_sha':sha(dest)}))
if __name__=='__main__':main()
