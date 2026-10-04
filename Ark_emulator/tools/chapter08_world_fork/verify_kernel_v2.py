import sys,json,hashlib,contextlib,io,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ap=argparse.ArgumentParser();ap.add_argument('--runtime',required=True);ap.add_argument('--core',required=True);ap.add_argument('--output',required=True);ap.add_argument('--old-counter-only',action='store_true');args=ap.parse_args();RUNTIME=Path(args.runtime).resolve();OUT=ROOT/'validation/campaign'/args.output;OUT.mkdir(exist_ok=False);sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT));sys.path.append(str(ROOT/'tests_v2'))
import pytest
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();selection=['tools/chapter08_world_fork/test_author_v1.py'] if args.old_counter_only else ['tools/chapter08_world_fork/test_author_v1.py','tests_v2/test_kernel.py','tests_v2/test_m6_kernel_review.py'];files=[Path(__file__)]+[ROOT/x for x in selection]+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.suffix in ('.py','.json')]
def guards():return {str(p):sha(p) for p in sorted(set(files))}
before=guards();assert implementation_digest()==args.core
class Plugin:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call':self.rows.append({'nodeid':report.nodeid,'outcome':report.outcome,'duration':report.duration,'failure':str(report.longrepr) if report.failed else None})
plugin=Plugin();buf=io.StringIO()
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main(selection+['-q','--import-mode=importlib'],plugins=[plugin])
after=guards();r={'passed':code==0 and before==after,'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Authoractualkernel/fork boundary tests, not independent peer/full/base; oldcounter flags keep actualfail outcomes.'};(OUT/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))

