"""Collection-order hint for a running pytest progress failure, not final evidence."""
import contextlib,io,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));import ark_sim
def main():
 import pytest
 collected=[]
 class Collector:
  def pytest_collection_finish(self,session):collected.extend(i.nodeid for i in session.items)
 with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):code=int(pytest.main([str(ROOT/'tests_v2'),'--collect-only','-q'],plugins=[Collector()]))
 assert code==0
 chars=''.join(m.group(1) for line in (OUT/'full_suite.log').read_text(encoding='utf8').splitlines() if (m:=re.match(r'^([.FsxXE]+)(?:\s|$)',line)))
 candidates=[{'progress_index':i,'nodeid_collection_hint':collected[i],'status':c} for i,c in enumerate(chars) if c in 'FE']
 print(json.dumps({'collected':len(collected),'progress_statuses_seen':len(chars),'failure_order_hints':candidates,'actual_final_failure_report_pending':True}))
if __name__=='__main__':main()
