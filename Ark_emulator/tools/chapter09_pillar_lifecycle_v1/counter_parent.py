import sys,json,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str((ROOT/'../unpack_work/campaign_c9_depletion_v2_candidate').resolve()))
sys.path.insert(1,str(ROOT))
from tools.chapter09_depletion.test_depletion_v2 import data,registry,zero
from tools.chapter09_pillar_v1.build_payload import build
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
d=data();s=Engine.create(Compiler(providers=registry()).compile(d),providers=registry());zero(s);s.session.advance(61)
before=s.checkpoint()
try:s.ctx.abilities.start('target','ability/depletion/hit')
except ValueError as error:failure=str(error)
else:raise AssertionError('Parent unexpectedly authorizes depleted cast')
assert s.checkpoint()==before
decl=copy.deepcopy(d);decl['entities'][1]['components']['depletion']['actions']['ready']['owned_ability']='ability/depletion/hit'
try:Compiler(providers=registry()).compile(decl)
except ValueError as error:declaration=str(error)
else:raise AssertionError('Parent unexpectedly implements bridge declaration')
r={'core':implementation_digest(),'actual_counter_reproduced':True,'ready_hp':s.ctx.resources.current('target','hp'),'ready_alive':s.ctx.alive('target'),'ordinary_start_rejection':failure,'owned_declaration_rejection':declaration,'whole_pillar_complete':False}
(ROOT/'validation/campaign/chapter09_pillar_lifecycle_v1/parent.counter.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
