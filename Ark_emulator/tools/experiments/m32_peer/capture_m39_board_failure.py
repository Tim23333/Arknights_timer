import json,hashlib
from pathlib import Path
import test_m39_fields as h
p=h.scene();board={'definition':'unit/owner','tags':['player'],'components':{'abilities':['not/an/ability']},'provider':'unregistered'};p['scenarioDraft']['map']['tile_mechanics']['custom_field']['expected_blackboard']=board;p['scenarioDraft']['map']['tiles'][1]['blackboard']=board
try:h.Compiler().compile(p);error=None
except ValueError as e:error=str(e)
assert error is not None and 'not/an/ability' in error;report={'schema':'ark-sim/map-board-reference-scope-counterexample/v1','core':h.implementation_digest(),'module':h.ark_sim.__file__,'fixture':p,'expected':'compile accepted because all map BB and expectedboard are explicit data','actual_compile_error':error,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'passed':False};out=h.ROOT/'validation/campaign/m32_peer/nested_board_m39_failure.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(hashlib.sha256(out.read_bytes()).hexdigest())
