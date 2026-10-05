import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str((ROOT/'../unpack_work/campaign_c9_duspfr_v1_candidate').resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
p={'schemaVersion':2,'buffs':[{'id':'buff/record','kind':'buff','duration_seconds':25}],'entities':[{'id':'unit/record','kind':'entity','dependencies':['buff/record'],'components':{'attributes':{'base':{'max_hp':50000}},'resources':{'hp':{'role':'health','initial':50000,'capacity':50000}},'spatial':{}}}],'scenarioDraft':{'id':'scene/record','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'initialEntities':[{'definition':'unit/record','instanceAlias':'source','position':{'row':0,'col':0}}]}}
s=Engine.create(Compiler().compile(p));s.ctx.resources.adjust('source','hp',value=40000);uid=s.ctx.buffs.apply('source','source','buff/record');row=next(b for b in s.ctx.get('source',('buffs','instances')) if b['id']==uid);assert row['blackboard']=={}
p['buffs'][0]['capture']={'rule':'rule/capture','refresh':'retain','parameters':{'offset':-.4}}
try:Compiler().compile(p)
except ValueError as error:failure=str(error)
else:raise AssertionError('Unexpected capture implementation')
r={'core':implementation_digest(),'actual_counter_reproduced':True,'actual_hp_on_buff_start':40000,'actual_blackboard':row['blackboard'],'expected_recorded_hp_ratio_offset':.4,'new_capture_declaration_rejection':failure,'composition_examined':'Buff instance blackboard exists but apply initializes empty/preserves previous; application pure plan only apply/remove/duration/stacks, no source sample record operation'};(ROOT/'validation/campaign/chapter09_mandra_v1/parent.capture.counter.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
