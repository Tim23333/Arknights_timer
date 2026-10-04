import sys,json,argparse,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-digest',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sys.path.insert(0,str(a.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
assert implementation_digest()==a.expected_digest

def dynamic_tile(i,p,c):
 open=c['time']>=6;return {**i['base'],'passableMask':1 if open else 0,'groundPassable':open,'movementCost':1}
dynamic_tile.version='peer-time-six-open-1'
providers={**BUILTIN_PROVIDERS,'peer.dynamic':dynamic_tile}
p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/owner','kind':'entity','components':{'spatial':{},'terrain_overlays':[{'key':'gate','priority':0,'values':{},'rule':'rule/dynamic'}]}},{'id':'unit/walker','kind':'entity','tags':['enemy','ground'],'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'move_speed':3}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],'rules':[{'id':'rule/dynamic','kind':'calculation_rule','contract':'terrain.tile_options','implementation':{'type':'provider','provider':'peer.dynamic'}}],'scenarioDraft':{'id':'scenario/independent_dynamic','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},'initialEntities':[{'definition':'unit/owner','instanceAlias':'owner','position':{'row':0,'col':1}},{'definition':'unit/walker','instanceAlias':'walker','position':{'row':0,'col':0},'route':{'motionMode':'WALK','endPosition':{'row':0,'col':4}}}]}}
s=Engine.create(Compiler(providers=providers).compile(p),providers=providers,seed=1621);s.advance(6);assert s.ctx.get('walker',('spatial','position'))=={'row':0,'col':0};saved=s.checkpoint()
for _ in range(4):assert s.ctx.spatial.grid.tile(0,1)['groundPassable'] is True
assert s.checkpoint()==saved
r=Engine.restore(s.program,saved,providers=providers);assert r.ctx.spatial.grid.tile(0,1)['groundPassable'] is True;s.advance(3);r.advance(3);assert s.snapshot()==r.snapshot();assert abs(s.ctx.get('walker',('spatial','position'))['col']-.3)<1e-9;assert s.snapshot()==replay(s.program,s.export_replay(),providers=providers).snapshot()
assert s.ctx.get('system/battle',('state','terrain','revision'))==2
assert implementation_digest()==a.expected_digest
report={'schema':'ark-sim/independent-dynamic-terrain-review/v1','passed':True,'implementation_sha256':a.expected_digest,'runtime_module':sys.modules['ark_sim'].__file__,'pure_getter_checkpoint_unchanged':True,'time_rule_no_world_cache_stale':True,'actual_walker_at9':s.ctx.get('walker',('spatial','position')),'checkpoint_equal':True,'replay_equal':True,'commands':s.export_replay(),'fixture':p,'events':thaw([e for e in s.session.events if e['type'] in ('terrain.changed','movement.traveled')]),'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed'}],'formal_approval':False}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'core':a.expected_digest,'revision':2}))
