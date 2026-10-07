"""Source physical/arts/heal golden with explicitly enemy-qualified recipient."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';OUT=ROOT/'validation/trace_audit/source_golden_v3';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.trace_audit.capture_source_golden_v1 import CORE
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==CORE;OUT.mkdir(parents=True,exist_ok=True);parent=ROOT/'validation/trace_audit/source_golden_v2/input.json';p=json.loads(parent.read_bytes());p['scenarioDraft']['id']='scene/source_audit_golden_v3';target=next(d for d in p['definitions'] if d['id']=='unit/audit_controlled_enemy');target['tags']=['enemy'];p['scenarioDraft']['metadata']['controlled_fixture']='Only stationary test recipient enemy qualification changed; all true source actor definitions/numbers retained.';amy=p['scenarioDraft']['roster'][0];inp=OUT/'input.json';journal=OUT/'events.jsonl';assert not inp.exists() and not journal.exists();inp.write_text(json.dumps(p,indent=2)+'\n',encoding='utf8',newline='');s=Engine.create(Compiler().compile(p),event_journal_path=journal);cmd={'action':'deploy','entity':amy,'row':2,'col':3,'facing':'right','alias':'arts_source'};s.submit(cmd,at=930);s.session.advance(1100);damage=[];heal=[];started=[];commands=[]
 with journal.open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line)
   if e['type']=='damage.accepted':damage.append(e)
   if e['type']=='regeneration.accepted':heal.append(e)
   if e['type']=='ability.started':started.append(e)
   if e['type'].startswith('command.'):commands.append(e)
 snap=OUT/'snapshot.json';snap.write_text(json.dumps(s.snapshot(),indent=2)+'\n',encoding='utf8',newline='');pins=ROOT/'validation/trace_audit/source_golden_v2/oracle_pins.json';result={'core':CORE,'parent_fixture_sha':sha(parent),'input_sha':sha(inp),'journal_sha':sha(journal),'snapshot_sha':sha(snap),'oracle_pins_path':str(pins),'oracle_pins_sha':sha(pins),'helper_sha':sha(Path(__file__)),'source_units_bytewise_definition_equal_to_parent':True,'recipient_tag_delta_explicit':True,'damage_events':damage,'regeneration_events':heal,'ability_started':started,'actual_command_events':commands,'client_verified':False};dest=OUT/'capture.json';dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');assert implementation_digest()==CORE;print(json.dumps({'damage':len(damage),'heal':len(heal),'abilities':started,'receipt_sha':sha(dest)}))
if __name__=='__main__':main()
