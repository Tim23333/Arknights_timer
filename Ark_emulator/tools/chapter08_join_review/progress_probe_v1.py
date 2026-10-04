"""Read-only runtime diagnostic for a long firstdown proof; no monkeypatch."""
import json
from tools.chapter08_join_review.review_v2 import package,providers,CORE,ROOT,sha
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/chapter08_join_progress_v1'
def main():
    assert implementation_digest()==CORE;OUT.mkdir(exist_ok=True);p=package(True)
    s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=101804)
    (OUT/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode())
    for end in (100,151,212,752,990,991,992,1000,1100):
        s.session.advance(end-s.session.time)
        row={'time':s.session.time,'events':len(s.session.events),'hp':s.ctx.resources.current('boss','hp'),'active':s.ctx.active('boss'),'mode':s.ctx.resources.current('boss','mode')}
        print(json.dumps(row),flush=True)
        with (OUT/'progress.jsonl').open('ab') as f:f.write((json.dumps(row)+'\n').encode())
    assert implementation_digest()==CORE
if __name__=='__main__':main()
