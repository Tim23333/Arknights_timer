import sys,json,argparse,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
a=argparse.ArgumentParser();a.add_argument('--runtime-root',type=Path,required=True);a.add_argument('--expected-digest',required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.adapters.api import implementation_digest
assert implementation_digest()==args.expected_digest

def template():
 return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/owner','kind':'entity','components':{'spatial':{},'terrain_overlays':[{'key':'x','priority':0,'values':{'buildableType':0},'rule':'rule/peer'}]}}],'rules':[{'id':'rule/peer','kind':'calculation_rule','contract':'terrain.tile_options','implementation':{'type':'provider','provider':'peer.tile'}}],'scenarioDraft':{'id':'scenario/peer','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2,'tiles':[{'tileKey':'tile_floor','buildableType':1,'passableMask':1,'blackboard':None,'effects':None}]*2},'initialEntities':[{'definition':'unit/owner','instanceAlias':'owner','position':{'row':0,'col':0}}]}}

def bad(i,p,c):return {**i['base'],'tileKey':'unsupported_behavior_key','blackboard':{'must_not_ignore':True},'effects':[{'unknown':True}],'groundPassable':True,'movementCost':1}
def partial(i,p,c):return {'buildableType':2,'passableMask':3,'groundPassable':True,'movementCost':7,'physicalHeight':.75}
def portal_replace(i,p,c):return {**i['base'],'tileKey':'custom_exit','groundPassable':True,'movementCost':1}
for f in (bad,partial,portal_replace):f.version='independent-tile-identity-boundary-1'
results=[]
for name,fn,reject in [('unknown_behavior',bad,True),('numeric_partial',partial,False),('portal_replace',portal_replace,True)]:
 p=template()
 if name=='portal_replace':p['scenarioDraft']['map']['tiles'][0]['tileKey']='custom_entry';p['scenarioDraft']['map']['tile_mechanics']={'custom_entry':{'type':'route_checkpoint_portal','role':'entry'},'custom_exit':{'type':'route_checkpoint_portal','role':'exit'}}
 providers={**BUILTIN_PROVIDERS,'peer.tile':fn};observed=None;error=None
 try:s=Engine.create(Compiler(providers=providers).compile(p),providers=providers);observed=s.ctx.spatial.grid.tile(0,0)
 except ValueError as e:error=str(e)
 passed=(error is not None) if reject else (error is None and observed.get('tileKey')=='tile_floor' and 'blackboard' in observed and observed['blackboard'] is None and 'effects' in observed and observed['effects'] is None and observed['movementCost']==7 and observed['physicalHeight']==.75)
 results.append({'case':name,'expected_rejected':reject,'passed':passed,'actual_tile':observed,'error':error,'fixture':p})
assert implementation_digest()==args.expected_digest
report={'schema':'ark-sim/independent-tile-rule-boundary/v1','passed':all(r['passed'] for r in results),'implementation_sha256':implementation_digest(),'runtime_module':sys.modules['ark_sim'].__file__,'cases':results,'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed' if all(r['passed'] for r in results) else 'failed'}],'scope':'Actual compile/create/getter boundary, no fake simulation; partial-world expected rejection for unsupported behaviors. No command replay claim for rejected/API getter fixtures','formal_approval':False}
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':[(r['case'],r['passed']) for r in results]}))
