import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str((ROOT/'../unpack_work/campaign_c9_duspfr_v1_candidate').resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
p={'schemaVersion':2,'rules':[{'id':'rule/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity'}}],'behaviors':[{'id':'behavior/modes','kind':'behavior','initial':'mode0','states':{'mode0':{},'mode2':{}},'transitions':[]}],'entities':[{'id':'unit/modes','kind':'entity','components':{'attributes':{'base':{'max_hp':50000}},'resources':{'hp':{'role':'health','initial':50000,'capacity':50000}},'spatial':{},'behavior':{'machine':'behavior/modes'},'lifecycle':{'policy':'policy/ark_lifecycle'},'rebirth':{'resource':'hp','max_count':1,'delay_seconds':5,'restore_ratio':1,'restore_rule':'rule/restore','on_begin':[{'op':'transition','state':'mode2'}]}}}],'scenarioDraft':{'id':'scene/waiting-mode','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'initialEntities':[{'definition':'unit/modes','instanceAlias':'source','position':{'row':0,'col':0}}]}}
s=Engine.create(Compiler().compile(p));before=s.checkpoint()
try:s.ctx.resources.adjust('source','hp',value=0)
except ValueError as error:failure=str(error)
else:raise AssertionError('Parent unexpectedly supports waiting mode transition')
assert s.checkpoint()==before
r={'core':implementation_digest(),'actual_counter_reproduced':True,'error':failure,'actual_full_zero_transaction_rollback':True,'source_need':'BSON Reborn ON_BUFF_START SwitchMode2 occurs during owned zero-health waiting period'};(ROOT/'validation/campaign/chapter09_mandra_v1/parent.waiting_mode.counter.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
