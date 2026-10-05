import sys,json,io,contextlib,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_mandra_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
before=implementation_digest();stream=io.StringIO()
with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):code=pytest.main([str(ROOT/'tests_v2/test_domain_rules.py'),'-q','--basetemp=E:/ArkSimLogs/runs/chapter09_mandra_domain46_final_v2/temp'])
clean=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs_v2.py'),'--run-dir','E:/ArkSimLogs/runs/chapter09_mandra_domain46_final_v2','--apply','--minimum-age-minutes','0','--completed-pid',str(os.getpid())],capture_output=True,text=True,encoding='utf8')
r={'core_before':before,'core_after':implementation_digest(),'actual_exit':int(code),'imported_package':ark_sim.__file__,'stdout':stream.getvalue(),'cleanup':json.loads(clean.stdout)};(ROOT/'validation/campaign/chapter09_mandra_v1/author.domain46.final.v2.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r));raise SystemExit(code or clean.returncode)
