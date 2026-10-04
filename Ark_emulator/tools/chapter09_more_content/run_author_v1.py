"""Reproducible focused author gate with mandatory temporary log cleanup."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter09_more_content.build_v1 import CORE,OUT,KEYS,sha
LOG=Path('E:/ArkSimLogs/runs/chapter09_more_author_v1')
def main():
 result=subprocess.run([sys.executable,'-m','pytest','tools/chapter09_more_content/test_v1.py','-q','--basetemp','E:/ArkSimLogs/runs/chapter09_more_pytest_v2'],cwd=ROOT,capture_output=True,text=True)
 clean=subprocess.run([sys.executable,'tools/cleanup_simulation_logs.py','--apply','--run-dir',str(LOG),'--minimum-age-minutes','0'],cwd=ROOT,capture_output=True,text=True)
 if clean.returncode==0:
  for case in (ROOT/'validation/campaign/chapter09_more_author').glob('*/receipt.json'):
   value=json.loads(case.read_bytes());value.update(log_cleanup_required=False,CP_deleted_after_verification=True);case.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
 receipt={'runtime':CORE,'focused_test_exit_code':result.returncode,'pytest_summary':result.stdout.splitlines()[-1] if result.stdout else '', 'cleanup_exit_code':clean.returncode,'cleanup':json.loads(clean.stdout) if clean.returncode==0 else clean.stderr,'module_sha':{k:sha(OUT/(k+'.module.v1.json')) for k in KEYS},'whole_stage':False,'independent_reviewed':False,'client_verified':False}
 path=ROOT/'validation/campaign/chapter09_more_author/author.receipt.v1.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt));return result.returncode or clean.returncode
if __name__=='__main__':sys.exit(main())
