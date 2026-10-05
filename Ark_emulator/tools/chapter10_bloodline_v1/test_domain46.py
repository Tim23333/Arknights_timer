"""Original domain tests on isolated candidate, unchanged test expectations."""
import sys,os,json,io,contextlib,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_bloodline_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest
files=[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p):sha(p) for p in files};core=implementation_digest();stream=io.StringIO()
with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):code=pytest.main([str(ROOT/'tests_v2/test_domain_rules.py'),'-q','--basetemp='+str(Path(os.environ['ARKSIM_RUN_DIR'])/'temp')])
after={str(p):sha(p) for p in files};report={'core_before':core,'core_after':implementation_digest(),'actual_exit':int(code),'source_before':before,'source_after':after,'source_equal':before==after,'imported_package':ark_sim.__file__,'stdout':stream.getvalue()};p=ROOT/'validation/campaign/chapter10_bloodline_v1/domain46.initial.v1.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':int(code),'source_equal':before==after}));raise SystemExit(int(code) if code else 0 if before==after else 1)
