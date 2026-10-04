"""Run actual author/peer boundaries against the newly imported composite."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m91_complete_c4_candidate';OUT=ROOT/'validation/campaign/m91_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import ark_sim
from ark_sim.adapters.api import implementation_digest
PIN='e370d26ed84e5ac95feea9af51ac038f57ab7b7c22d943dd2116a99b50006feb'
TESTS=['tools/experiments/m78_attachments/test_attachment.py','tools/experiments/m86_immunity_environment/test_cross.py','tools/experiments/m86_immunity_environment/test_frost_combo.py','tools/experiments/m84_catalog_peer/test_peer.py','tools/experiments/m84_boundary_settle/test_kernel_boundary.py','tools/experiments/m81_root_peer/test_protocol.py','tools/experiments/m85_root_peer/test_sequence.py','tools/experiments/m75_packet_order/test_packets.py','tools/experiments/m72_no_source_damage/test_no_source.py','tests_v2/test_kernel.py','tests_v2/test_abilities.py','tests_v2/test_activation_controls.py','tests_v2/test_buff_mode_lifecycle.py','tests_v2/test_replay.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guards():
 paths=list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))+[ROOT/t for t in TESTS]+list(Path(__file__).parent.glob('*.py'))
 paths += [ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/finish_pending_disk_runthrough_v16.py',ROOT/'tools/run_campaign_disk_runthrough_v15.py',ROOT/'tools/build_chapter04_09_stage.py',ROOT/'packages/campaign/chapter04_dmage/module.reference.json',ROOT/'packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json']
 return {str(p.resolve()):sha(p) for p in paths}
def main():
 import pytest
 assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==PIN
 before=guards();cases=[]
 class Capture:
  def pytest_runtest_logreport(self,report):
   r=report
   if r.when=='call':cases.append({'case':r.nodeid,'outcome':r.outcome,'seconds':r.duration,'failure':str(r.longrepr) if r.failed else None})
 code=int(pytest.main([*[str(ROOT/t) for t in TESTS],'-q','--tb=short','-k','not optional_actual_epoch_change'],plugins=[Capture()]))
 after=guards();assert before==after and implementation_digest()==PIN
 report={'core':PIN,'actual_import':ark_sim.__file__,'exitcode':code,'cases':cases,'guards_before':before,'guards_after':after,'source_catalog_helper_stable':True,'whole_stage_executed':False,'client_verified':False}
 (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='')
 print(json.dumps({'exitcode':code,'passed':sum(r['outcome']=='passed' for r in cases),'failed':sum(r['outcome']=='failed' for r in cases),'report_sha256':sha(OUT/'verification.json')}))
 raise SystemExit(code)
if __name__=='__main__':main()
