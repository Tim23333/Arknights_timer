"""Current exact import tests; legal independent v3 lease boundary included."""
import argparse,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim
TESTS=['tools/experiments/m78_attachments/test_attachment.py','tools/experiments/m78_independent_controller_peer_v3/test_peer.py','tools/experiments/m86_immunity_environment/test_cross.py','tools/experiments/m86_immunity_environment/test_frost_combo.py','tools/experiments/m84_catalog_peer/test_peer.py','tools/experiments/m84_boundary_settle/test_kernel_boundary.py','tools/experiments/m81_root_peer/test_protocol.py','tools/experiments/m85_root_peer/test_sequence.py','tools/experiments/m75_packet_order/test_packets.py','tools/experiments/m72_no_source_damage/test_no_source.py','tests_v2/test_kernel.py','tests_v2/test_abilities.py','tests_v2/test_activation_controls.py','tests_v2/test_buff_mode_lifecycle.py','tests_v2/test_replay.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 paths=[ROOT/t for t in TESTS]+list(Path(__file__).parent.glob('*.py'))+[ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py',ROOT/'packages/campaign/chapter04_dmage/source.reference.json',ROOT/'packages/campaign/chapter04_dmage/module.reference.json',ROOT/'packages/campaign/chapter04_dmage/module.combat_guard.reference.json',ROOT/'packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json']
 paths += [p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
 return {str(p):sha(p) for p in paths}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--expected-core',required=True);args=ap.parse_args();assert implementation_digest()==args.expected_core and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
 import pytest
 sys.path.append(str(ROOT/'tests_v2'))
 before=guard();cases=[]
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
 code=int(pytest.main([*[str(ROOT/t) for t in TESTS],'-q','--tb=short','--import-mode=importlib','-k','not optional_actual_epoch_change and not normal_source2_actual_blocker_hard_eligibility'],plugins=[Results()]))
 after=guard();assert before==after and implementation_digest()==args.expected_core
 report={'core':args.expected_core,'exitcode':code,'cases':cases,'guard_before':before,'guard_after':after,'excluded_original_source_case':'v3 normal_source2 fixture still consumes immutable old module with already saved content failure; current M92 source guard independent receipt separate','whole_stage_executed':False,'client_verified':False}
 dest=OUT/'verification_current_run3.json';dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'exitcode':code,'passed':sum(c['outcome']=='passed' for c in cases),'report_sha':sha(dest)}));raise SystemExit(code)
if __name__=='__main__':main()
