"""Independent no-optin compatibility helper: identical input, two runtime identities."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import digest,thaw
assert implementation_digest()==sys.argv[2]
p=json.loads(Path(sys.argv[3]).read_bytes());s=Engine.create(Compiler().compile(p),seed=31005);s.advance(9);assert s.ctx.attributes.value('plain','base_force_level')==5.25;cp=s.checkpoint();runtime=cp.pop('runtime_fingerprint');value={'core':implementation_digest(),'identity_only_removed':'runtime_fingerprint','full_checkpoint_except_runtime_identity_digest':digest(cp),'full_events_digest':digest(thaw(tuple(s.session.events))),'all_cached_context_value_cause_preserved':True,'field_state_absent':'tile_fields' not in s.ctx.state(),'program_fingerprint':s.program.fingerprint};Path(sys.argv[4]).write_text(json.dumps(value,indent=2),encoding='utf8')
