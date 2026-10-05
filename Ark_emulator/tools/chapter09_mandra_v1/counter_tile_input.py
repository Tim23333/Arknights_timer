import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str((ROOT/'../unpack_work/campaign_c9_duspfr_v1_candidate').resolve()))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
p={'schemaVersion':2,'abilities':[{'id':'ability/input','kind':'ability','activation':{'mode':'manual'},'tile_selector':{'eligibility_expression':'inputs.cell.row == inputs.input.position.row and inputs.cell.col == inputs.input.position.col','parameters':{},'limit':1,'selection':'row_major','stream':None,'accept_input':True},'timeline':[]}],'entities':[{'id':'unit/input','kind':'entity','components':{'spatial':{},'abilities':['ability/input']}}],'scenarioDraft':{'id':'scene/input','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/input','position':{'row':0,'col':0}}]}}
try:Compiler().compile(p)
except ValueError as error:failure=str(error)
else:raise AssertionError('Parent unexpectedly supports input-target tile cast')
r={'core':implementation_digest(),'actual_counter_reproduced':True,'error':failure,'source_need':'Ray target Buff ON_OWNER_FINISH starts possessed source TileSpawn on the actual victim root tile; old selector has no input payload channel'};(ROOT/'validation/campaign/chapter09_mandra_v1/parent.tile_input.counter.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
