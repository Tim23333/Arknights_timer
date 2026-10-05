"""Complete cross-core nooptin state/metadata capture for explicit identity audit."""
import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
assert implementation_digest()==sys.argv[2]
p=json.loads(Path(sys.argv[3]).read_bytes());pr=Compiler().compile(p);s=Engine.create(pr,seed=31005);s.advance(9);assert s.ctx.attributes.value('plain','base_force_level')==5.25
out={'core':implementation_digest(),'checkpoint':s.checkpoint(),'program':{'scenario':thaw(pr.scenario),'definitions':thaw(pr.definitions),'ruleset':thaw(pr.ruleset),'rules':thaw(pr.rules),'metadata':thaw(pr.metadata),'dependency_ids':list(pr.dependency_ids),'fingerprint':pr.fingerprint}}
Path(sys.argv[4]).parent.mkdir(parents=True,exist_ok=True);Path(sys.argv[4]).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
