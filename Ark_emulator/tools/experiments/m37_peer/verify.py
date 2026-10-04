import sys,io,contextlib,json,hashlib,time,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m37_projectile_refs_candidate';BASE=ROOT.parent/'unpack_work/campaign_m30_projectile_quota_candidate';sys.path.insert(0,str(RUNTIME));OUT=ROOT/'validation/campaign/m37_peer'
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
import test_refs as h
CORE=h.CORE;sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
class Rows:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.rows.append({'case':report.nodeid,'result':report.outcome,'seconds':report.duration})
def main():
 assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';files=[Path(__file__),Path(__file__).with_name('test_refs.py'),ROOT/'tools/experiments/m30_quota/test_quota.py',RUNTIME/'ark_sim/domains/projectiles.py'];before={str(p):sha(p) for p in files};plugin=Rows();log=io.StringIO();begun=time.time()
 with contextlib.redirect_stdout(log):code=pytest.main(['tools/experiments/m37_peer/test_refs.py','-q','--tb=short'],plugins=[plugin])
 (OUT/'tests.log').write_text(log.getvalue(),encoding='utf8');assert code==0;old=(BASE/'ark_sim/domains/projectiles.py').read_text(encoding='utf8');new=(RUNTIME/'ark_sim/domains/projectiles.py').read_text(encoding='utf8');assert new.replace("  target=self.ctx.session.world.resolve(target)\n",'',1)==old;assert all(sha(Path(p))==v for p,v in before.items()) and implementation_digest()==CORE
 report={'schema':'ark-sim/projectile-canonical-reference-peer/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),'actual_module':ark_sim.__file__,'source_before':before,'source_after':{p:sha(Path(p)) for p in before},'tests':plugin.rows,'elapsed_seconds':time.time()-begun,'actual_code_difference':'exactly world.resolve(target) after trace-target fallback, before quota/invalid/inflight checks','scope':'same-canonical-runtime-ID quota/target-history consistency for alias/int caller paths; private API instrumentation separate from one ordinary command CP/replay case','invalid_alias_refs_no_mutation':True,'alias_repeat_allowed_only_under_same_target_and_cap_policy':True,'native_or_whole_stage_approval':False};out=OUT/'final_review.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'cases':len(plugin.rows),'sha256':sha(out)}))
if __name__=='__main__':main()
