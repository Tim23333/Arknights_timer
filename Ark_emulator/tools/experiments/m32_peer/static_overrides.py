"""Independent effective-instance/static-role gate counterexamples."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m32_static_tile_field_candidate';sys.path.insert(0,str(RUNTIME))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
CORE='5acf1c0e36d6d41b04fc2fdf4ec1677eeed6e93949a0d97f5776088f38404456'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def scene():
 return {'entities':[{'id':'unit/owner','kind':'entity','tags':['tile_field_owner'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1,'atk':0}},'resources':{'hp':{'initial':1,'capacity':1}},'buffs':{'initial':['buff/parent']}}},{'id':'unit/target','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'def':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}}}}],
 'buffs':[{'id':'buff/parent','kind':'buff','aura':{'selector':'selector/cell','buff':'buff/member'}},{'id':'buff/member','kind':'buff','stacking':{'mode':'independent'},'modifiers':[]}],
 'selectors':[{'id':'selector/cell','kind':'selector','region':{'type':'grid_offsets','offsets':[[0,0]],'rotate_with_facing':False},'filters':[{'tag':'player'}]},{'id':'selector/target','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1}],
 'abilities':[{'id':'ability/illegal_owner','kind':'ability','selector':'selector/target','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'physical'}]},'timeline':[]}],
 'scenarioDraft':{'id':'scenario/static_override_counter','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4,'tiles':[{'tileKey':'tile_floor','buildableType':1,'passableMask':1},{'tileKey':'custom_field','buildableType':1,'passableMask':1,'blackboard':[]},{'tileKey':'tile_floor','buildableType':1,'passableMask':1},{'tileKey':'tile_floor','buildableType':1,'passableMask':1}],'tile_mechanics':{'custom_field':{'type':'occupancy_buff_field','definition':'unit/owner','expected_blackboard':{}}}},'objectives':{},'initialEntities':[{'definition':'unit/target','instanceAlias':'target','position':{'row':0,'col':2}}]}}
def run():
 assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';rows=[]
 for case,override in [('initial_abilities',{'abilities':['ability/illegal_owner'],'attributes':{'base':{'atk':50}}}),('initial_route',{'attributes':{'base':{'move_speed':3}},'spatial':{'route':{'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}}})]:
  p=scene();p['scenarioDraft']['initialEntities'].append({'definition':'unit/owner','instanceAlias':'clone','position':{'row':0,'col':0},'components':override});compiled=True
  try:program=Compiler().compile(p)
  except ValueError as e:rows.append({'case':case,'expected':'compile_rejected','actual_compile_rejected':True,'reason':str(e),'fixture':p});continue
  s=Engine.create(program,seed=3201)
  if case=='initial_abilities':s.submit({'action':'skill','source':'clone','ability':'ability/illegal_owner'},at=0)
  s.advance(3);rows.append({'case':case,'expected':'compile_rejected','actual_compile_rejected':False,'fixture':p,'commands':s.export_replay(),'clone_position':s.ctx.get('clone',('spatial','position')),'target_hp':s.ctx.resources.current('target','hp'),'events':thaw([e for e in s.session.events if e['type'] in ['command.accepted','command.rejected','damage.accepted','movement.displaced']]),'program':s.program.fingerprint,'runtime':s.runtime_fingerprint})
 report={'schema':'ark-sim/m32-static-effective-instance-peer/v1','passed':all(r['actual_compile_rejected'] for r in rows),'core_start':CORE,'core_end':implementation_digest(),'actual_module':ark_sim.__file__,'source_sha256':sha(__file__),'cases':rows,'scope':'authored static role must hold for effective instance components, not just base map owner definition','formal_approval':False};out=ROOT/'validation/campaign/m32_peer/static_override_original.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'actual':[(r['case'],r['actual_compile_rejected'],r.get('target_hp'),r.get('clone_position')) for r in rows],'sha256':sha(out)}))
if __name__=='__main__':run()
