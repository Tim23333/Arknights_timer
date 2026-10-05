import sys,json,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str((ROOT/'../unpack_work/campaign_c9_pillar_channel_joint_v1_candidate').resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_depletion.test_depletion_v2 import data,registry,zero,cp
d=data();d['entities'][1]['components']['abilities']=['ability/depletion/finish'];d['abilities'].append({'id':'ability/depletion/finish','kind':'ability','activation':{'mode':'manual','parameters':{'blocks_attacks':False}},'timeline':[{'at':0,'effect':{'op':'emit','event':'actual_area_entry'}}]});d['entities'][1]['components']['depletion']['actions']['begin']['owned_ability']='ability/depletion/finish'
s=Engine.create(Compiler(providers=registry()).compile(d),providers=registry());before=cp(s)
try:zero(s)
except ValueError as error:failure=str(error)
else:raise AssertionError('Parent unexpectedly supports non-tile finite cast')
assert cp(s)==before
d=data();d['abilities'][0]['trigger_selector']='selector/depletion/target'
try:Compiler(providers=registry()).compile(d)
except ValueError as error:trigger_failure=str(error)
else:raise AssertionError('Parent unexpectedly supports independent trigger selector')
report={'core':implementation_digest(),'actual_counter_reproduced':True,'non_tile_owned_callback':failure,'independent_trigger_radius':trigger_failure,'full_transaction_rollback':True,'parent_whole_suite_accepted':False};(ROOT/'validation/campaign/chapter09_duspfr_v1/parent.counter.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
