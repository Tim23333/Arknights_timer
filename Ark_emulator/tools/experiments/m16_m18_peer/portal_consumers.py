import sys,json,argparse,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-digest',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sys.path.insert(0,str(a.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.presets.providers import living_route_transition
assert implementation_digest()==a.expected_digest
POLICY={'rule':'rule/portal','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}}
def scene(map,origin,exit,wait):
 return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/walker','kind':'entity','tags':['enemy','ground'],'components':{'attributes':{'base':{'max_hp':100,'move_speed':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],'rules':[{'id':'rule/portal','kind':'calculation_rule','contract':'movement.transition','implementation':{'type':'provider','provider':'ark.movement.living_transition'}}],'scenarioDraft':{'id':'scenario/independent_portal','ruleset':'ruleset/ark_standard','map':deepcopy(map),'objectives':{},'initialEntities':[{'definition':'unit/walker','instanceAlias':'walker','position':origin,'route':{'motionMode':'WALK','startPosition':origin,'endPosition':exit,'transition_policy':deepcopy(POLICY),'checkpoints':[{'type':'DISAPPEAR'},{'type':'WAIT_FOR_SECONDS','time':wait},{'type':'APPEAR_AT_POS','position':exit}]}}]}}
results=[];package=json.loads((ROOT/'packages/campaign/chapter01_stage_models/m18/level_main_01-12.portal.partial.json').read_bytes());audit=json.loads((ROOT/'validation/campaign/chapter01_portal_source_audit.json').read_bytes());map=package['scenarioDraft']['map'];rows=map['rows']
for wait in (3,35,40):
 assoc=next(x for x in audit['route_associations'] if x['hidden_wait_seconds']==[wait]);origin={'row':rows-1-assoc['entry_nominal_position']['row'],'col':assoc['entry_nominal_position']['col']};exit={'row':rows-1-assoc['exit_position']['row'],'col':assoc['exit_position']['col']};p=scene(map,origin,exit,wait);s=Engine.create(Compiler().compile(p),seed=1821);s.advance(1);assert s.ctx.route_hidden('walker');saved=s.checkpoint();before=s.checkpoint()
 for _ in range(3):s.ctx.spatial.grid.tile(origin['row'],origin['col'])
 assert s.checkpoint()==before;s.advance(wait*30);r=Engine.restore(s.program,saved);r.advance(wait*30);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();assert not s.ctx.route_hidden('walker') and s.ctx.get('walker',('spatial','position'))==exit and s.ctx.get('walker',('spatial','distance_travelled'),0)==0
 ev=[e for e in s.session.events if e['type']=='movement.visibility_changed'];assert [e['time'] for e in ev]==[0,wait*30];assert all(e['payload']['tile_transition']['capture']['entry']['cell']==origin for e in ev)
 results.append({'case':'raw_route_excerpt_'+str(wait),'source_route_index':assoc['route_index'],'actual_exit':exit,'fixture':p,'checkpoint_equal':True,'replay_equal':True,'events':thaw(ev)})
# A custom transition must observe the fresh effective tile plus persisted entry.
def read_capture(i,p,c):
 t=i['tile_transition']
 if i['kind']==6:assert t['capture']['entry']['tile_options']['passableMask']==3 and t['origin']['tile_options']['passableMask']==1 and t['capture']['captured_at']==0
 return living_route_transition(i,p,c)
read_capture.version='independent-capture-effective-tile-1'
map={'rows':1,'cols':5,'tiles':[{'tileKey':('entry' if c==0 else 'exit' if c==3 else 'tile_floor'),'passableMask':3,'buildableType':0} for c in range(5)],'tile_mechanics':{'entry':{'type':'route_checkpoint_portal','role':'entry'},'exit':{'type':'route_checkpoint_portal','role':'exit'}}}
p=scene(map,{'row':0,'col':0},{'row':0,'col':3},.2);p['rules'][0]['implementation']['provider']='peer.read_capture';p['entities'].append({'id':'unit/owner','kind':'entity','components':{'spatial':{},'abilities':['ability/layer']}});p['abilities']=[{'id':'ability/layer','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_terrain_overlay','target':'source','parameters':{'key':'same_portal','priority':1,'values':{'passableMask':1,'physicalHeight':1}}}]},'timeline':[]}];p['scenarioDraft']['initialEntities'].append({'definition':'unit/owner','instanceAlias':'owner','position':{'row':0,'col':0}})
providers={**BUILTIN_PROVIDERS,'peer.read_capture':read_capture};s=Engine.create(Compiler(providers=providers).compile(p),seed=1822,providers=providers);s.submit({'action':'skill','source':'owner','ability':'ability/layer'},at=2);s.advance(3);assert s.ctx.route_hidden('walker');capture=s.ctx.get('walker',('spatial','portal_capture'));assert capture['entry']['tile_options']['passableMask']==3;saved=s.checkpoint();s.advance(4);r=Engine.restore(s.program,saved,providers=providers);r.advance(4);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers).snapshot();assert s.ctx.get('walker',('spatial','position'))=={'row':0,'col':3} and s.ctx.get('walker',('spatial','distance_travelled'),0)==0
results.append({'case':'capture_survives_terrain_and_custom_rule_consumes_fresh_origin','fixture':p,'checkpoint_equal':True,'replay_equal':True,'capture_before_restore':capture})
assert implementation_digest()==a.expected_digest
result={'schema':'ark-sim/independent-portal-consumers/v1','passed':True,'implementation_sha256':a.expected_digest,'runtime_module':sys.modules['ark_sim'].__file__,'cases':results,'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed'}],'scope':'Four real scenarios; source3/35/40 route excerpts only, not complete routes or stages. Command/API source shader and CP/replay scoped explicitly.','formal_approval':False}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'cases':len(results),'core':a.expected_digest}))
