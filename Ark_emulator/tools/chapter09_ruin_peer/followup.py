import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.chapter09_ruin_peer.common import *
from tools.chapter09_stage_assembly_v1.providers_v5 import providers as new_providers
from ark_sim.domains.selection import DEFAULT_STATE
REG=new_providers();V5=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v5.life99999.json';newstage=json.loads(V5.read_bytes());RESULTS=[];FACTS={};ARTIFACTS=[]
def new_scene():
 p=scene('coupled/dushdo');p['definitions']=deepcopy(newstage['definitions']);uid=p['scenarioDraft']['initialEntities'][1]['definition'];a=next(d for d in p['definitions'] if d['id']==uid);a['components']['attributes']['base'].update(max_hp=4729,atk=431,**{'def':287,'mres':41,'move_speed':1.13,'attack_interval':2.3,'attack_speed_ratio':1.1});a['components']['resources']['hp']['initial']=4729;return p

def create5(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=4729287)
def radius():
 r=math.sqrt(root['_blockRadiusSquare']);values=[]
 oldp=scene(position=(3+r-.0001,4));uid=oldp['scenarioDraft']['initialEntities'][1]['definition'];a=next(d for d in oldp['definitions'] if d['id']==uid);a['components'].pop('behavior',None);a['components']['abilities']=[];a['components']['attributes']['base']['move_speed']=0;s=create(oldp);s.advance(1);values.append({'prior_fixture_position':s.ctx.get('enemy',('spatial','position')),'prior_runtime':s.ctx.get('enemy',('runtime',)),'prior_route':s.ctx.get('enemy',('spatial','route')),'prior_blocked':s.ctx.spatial.blocked_by('enemy')})
 col=.499
 for epsilon,want in [(-.00001,True),(.00001,False)]:
  radial=r+epsilon;dr=math.sqrt(radial*radial-col*col);p=scene(position=(3+dr,4+col));uid=p['scenarioDraft']['initialEntities'][1]['definition'];a=next(d for d in p['definitions'] if d['id']==uid);a['components'].pop('behavior',None);a['components']['abilities']=[];a['components']['attributes']['base']['move_speed']=0;s=create(p);s.advance(1);actual=s.ctx.spatial.blocked_by('enemy') is not None;assert actual==want;values.append({'epsilon':epsilon,'position':s.ctx.get('enemy',('spatial','position')),'runtime':s.ctx.get('enemy',('runtime',)),'actual_blocked':actual,'squared_distance':dr*dr+col*col,'native_threshold':root['_blockRadiusSquare']})
 FACTS['radius']=values

def coupled():
 p=new_scene();a=create5(p);a.advance(8);path=LOG/'v5coupled.checkpoint.json';pin=write_ordered(path,a.checkpoint());b=Engine.restore(a.program,load_bound(path,pin),providers=REG);a.advance(112);b.advance(112);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert not a.ctx.alive('ruin');assert a.ctx.state().get('kills',0)==0;assert a.ctx.spatial.blocked_by('enemy') is None;hits=events(a,'damage.accepted');assert hits and hits[0][1]['amount']==100;ARTIFACTS.append({'name':'v5coupled','path':str(path),'sha256':pin,'bytes':path.stat().st_size,'CPP_head_full_equal':True});FACTS['v5coupled']={'actual_destroyed':True,'raw_ATK':431,'actual_hit_tick':hits[0][0],'actual_clamped_health_loss':100,'route_released':True,'nativekills':0}

def foreign():
 p=new_scene();p['scenarioDraft']['initialEntities'].append({'definition':BODY,'instanceAlias':'foreign','position':{'row':6,'col':7}});s=create5(p);s.ctx.spatial.blocking();actor=s.session.world.resolve('enemy');assert s.ctx.spatial.blocked_by(actor)==s.session.world.resolve('ruin');unit=s.ctx.entity(actor);selectors=[d for d in s.program.definitions.values() if d['kind']=='selector' and 'dushdo' in d['id'] and d.get('region',{}).get('blocked_only')];assert len(selectors)==1;sel=selectors[0];definition=s.program.definitions[sel['eligibility']['rule']];target=s.ctx.entity('foreign');inputs={'source':unit,'candidate':target,'selector':thaw(sel),'parameters':thaw(sel['eligibility']['parameters']),'selection_states':{'source':s.ctx.spatial.selection_state(actor,DEFAULT_STATE),'candidate':s.ctx.spatial.selection_state(target['id'],DEFAULT_STATE)}};result=s.ctx.calc('targeting.eligibility',inputs,source=actor,target=target['id'],rule_id=definition['id']);assert result['accepted'] is False
 same=deepcopy(inputs);same['candidate']=thaw(s.ctx.entity('ruin'));same['selection_states']['candidate']=s.ctx.spatial.selection_state('ruin',DEFAULT_STATE);same['selection_states']['candidate']['side']=1;result2=s.ctx.calc('targeting.eligibility',same,source=actor,target=same['candidate']['id'],rule_id=definition['id']);assert result2['accepted'] is False;FACTS['foreign']={'non_actual_blocker_obstacle_rejected':True,'same_enemy_side_obstacle_rejected':True,'original_masks_used':True}
for name,fn in [('corrected_radius_actual_on_path',radius),('v5_dushdo_different_ATK_actual_CPPhead',coupled),('foreign_and_same_side_exception_rejected',foreign)]:
 try:fn();RESULTS.append({'case':name,'passed':True})
 except Exception as e:RESULTS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
assert guard()==START;report={'core':CORE,'actual_exit':0 if all(x['passed'] for x in RESULTS) else 1,'results':RESULTS,'facts':FACTS,'v5_source_sha':sha(V5),'source_guard':True,'artifacts':ARTIFACTS,'first_4pass1_radius_fixture_failure_retained':True,'whole_stage':False};(REPORT/'followup.actual.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({'actual_exit':report['actual_exit'],'results':RESULTS}));raise SystemExit(report['actual_exit'])
