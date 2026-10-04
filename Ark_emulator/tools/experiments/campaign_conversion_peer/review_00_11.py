"""Independent 0-11 native field consumers and synchronous completion review."""
import sys,json,hashlib,base64,struct
from pathlib import Path
from collections import Counter
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m12_projection_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.extract_campaign_animation_bindings import unity_payload,parse_spine,resolve_animation,library_identity
import UnityPy
CORE='bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'
CONTENT='packages/campaign/mainline_models/level_main_00-11.m12_projection.json'
PIN='0c8736089ebd08b1768499c4e043486275c2ccdbbb08f4fa6c4007590f55a149'
def read(p):return json.loads((ROOT/p).read_bytes())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def write(p,v):(ROOT/p).write_text(json.dumps(thaw(v),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def ref(p,claim):return {'path':p,'sha256':sha(p),'claim':claim}
def roundtrip(sim):
 cp=sim.checkpoint();other=Engine.restore(sim.program,cp);sim.advance(2);other.advance(2);assert sim.snapshot()==other.snapshot();assert sim.snapshot()==replay(sim.program,sim.export_replay()).snapshot();return {'checkpoint_equal':True,'replay_equal':True,'program_fingerprint':sim.program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint}
def ui_probe(ui):
 from tools.experiments.m14_peer.verify import scene
 def fixture(empty):
  p=scene();actions=p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions']
  for action in ui:
   a=deepcopy(action)
   if empty:a['effects']=[]
   actions.insert(0,a)
  return p
 results=[]
 for empty in (False,True):
  p=fixture(empty);sim=Engine.create(Compiler().compile(p),seed=1411);sim.submit({'action':'skill','source':'killer','ability':'ability/peer_kill'},at=12);sim.advance(863)
  born=[e['time'] for e in sim.session.events if e['type']=='entity.created' and e['payload']['definition']=='unit/peer_enemy']
  # UI source pre27 and repeat28 plus captured fragment6 determine last action846; same zero-live
  # mathematical membership is enrolled/released synchronously, so wave delay
  # remains controlled by action completion plus post/pre clocks, never a UI actor.
  assert born==[6,861],born
  info=[e for e in sim.session.events if e['type']=='enemy.info_displayed'];story=[e for e in sim.session.events if e['type'].startswith('story.')];done=[e for e in sim.session.events if e['type']=='timeline.action' and e['payload']['kind']=='effects' and e['payload']['wave']==0 and e['payload']['fragment']==0]
  if not empty:
   assert [e['time'] for e in info]==[816,846]
   assert [e['type'] for e in story]==['story.started']+['story.command']*4+['story.finished'] and all(e['time']==6 for e in story)
   assert [e['time'] for e in done]==[6,816,846]
   for event in info+story:
    assert any(d['time']==event['time'] and d['id']>event['id'] for d in done)
   locks=[e for e in sim.session.events if e['type']=='input.lock_changed'];assert len(locks)==2 and all(e['time']==6 for e in locks)
  assert not sim.ctx.state().get('input_locks')
  results.append({'empty_zero_live_oracle':empty,'born_ticks':born,'control_events':info+story+done,'state':sim.ctx.state(),'roundtrip':roundtrip(sim)})
 assert results[0]['born_ticks']==results[1]['born_ticks'] and results[0]['state']['pending_waves']==results[1]['state']['pending_waves']
 return results

def route_probe(model):
 p=deepcopy(model);scene=p['scenarioDraft'];picked=[]
 for wave in scene['timeline']['waves']:
  for fragment in wave['fragments']:
   for a in fragment['actions']:
    if a['kind']=='spawn' and a['spawn']['parameters']['native_route_index'] in (13,14):
     x=deepcopy(a);x['delay_seconds']=0;picked.append(x)
 scene.update(id='scenario/peer_00_11_deadlines',roster=[],objectives={},timeline={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':1,'fragments':[{'pre_delay_seconds':2,'actions':picked}]}]})
 scene.setdefault('rules',{})['movement.checkpoint_position']='rule/m9_checkpoint_cartesian'
 sim=Engine.create(Compiler().compile(p),seed=1412);sim.advance(1100)
 waits=[e for e in sim.session.events if e['type']=='movement.wait'];assert len(waits)==2 and all(e['payload']['origin']==90 and e['payload']['until']==990 and e['time']<990 for e in waits)
 origins=[sim.ctx.get(e['payload']['source'],('spatial','timing_origins')) for e in waits];assert all(o['fragment_start']==90 and o['wave_start']==0 and o['action_start']==90 for o in origins)
 offset=sim.ctx.rules.evaluate('movement.checkpoint_position',{'position':{'row':4,'col':6},'offset':{'x':.44,'y':.44},'parameters':{'axis_signs':{'row':-1,'col':1}}},rule_id='rule/m9_checkpoint_cartesian',scope={},context={}).value
 assert abs(offset['row']-3.56)<1e-12 and abs(offset['col']-6.44)<1e-12
 return {'wait_events':waits,'timing_origins':origins,'offset_formula_output':offset,'roundtrip':roundtrip(sim),'scope':'Actual native routes13/14/definitions in isolated Timeline origins90; no fullstage rerun'}

def run():
 assert implementation_digest()==CORE and sha(CONTENT)==PIN
 model=read(CONTENT);nativep='packages/campaign/native_reference/level_main_00-11.json';native=read(nativep);source=read('packages/campaign/sources.00_11.reference.json');audit=read('packages/campaign/conversion_drafts/main_00-11.external.audit.json')
 for r in audit['source_locks']:assert sha(r['path'])==r['sha256']
 assert source['native_level_document']==native
 assert model['manifest']['metadata']['native_options']==native['options'] and model['manifest']['metadata']['inactive_native_runes']==native['runes'] and all(r['difficultyMask']=='FOUR_STAR' for r in native['runes'])
 assert all(not x for x in native['predefines'].values()) and not native['hardPredefines'] and not native['excludeCharIdList'] and not native['branches']
 opt=native['options'];scene=model['scenarioDraft'];assert scene['parameters']['deploy_capacity']==opt['characterLimit'] and scene['resources']['life']['initial']==opt['maxLifePoint'] and scene['resources']['dp']['initial']==opt['initialCost'] and scene['resources']['dp']['capacity']==opt['maxCost'] and scene['resources']['dp']['recovery']['interval_seconds']==opt['costIncreaseTime']
 assert next(r for r in model['rules'] if r['id']==scene['rules']['movement.speed'])['parameters']['multiplier']==opt['moveMultiplier']
 story=source['story'];raw=(ROOT.parent/story['source']['path']).read_bytes();payload=base64.b64decode(story['payload_base64']);assert raw[story['payload_offset']:story['payload_offset']+len(payload)]==payload and hashlib.sha256(payload).hexdigest()==story['payload_sha256'] and payload.decode('utf8')==story['script']
 actual_story=model['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][0]['effects'][0]['effects'];assert [e['payload'] for e in actual_story if e.get('event')=='story.command']==story['commands']
 rows=len(native['mapData']['map']);cols=len(native['mapData']['map'][0]);m=model['scenarioDraft']['map'];assert (m['rows'],m['cols'])==(rows,cols)
 build={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3};passing={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3};tiles=[]
 for row in native['mapData']['map']:
  for idx in row:
   t=deepcopy(native['mapData']['tiles'][idx]);assert t.pop('playerSideMask')=='ALL';t['buildableType']=build[t['buildableType']];t['passableMask']=passing[t['passableMask']];tiles.append(t)
 assert m['tiles']==tiles
 tl=model['scenarioDraft']['timeline'];assert tl['policy']=='managed_clear' and tl['negative_timeout_policy']=='wait_for_clear';assert len(tl['waves'])==len(native['waves'])==3
 population=Counter();wavecounts=[];ui=[];special=[];actions=0
 for wi,(nw,w) in enumerate(zip(native['waves'],tl['waves'])):
  assert [w[k] for k in ('pre_delay_seconds','post_delay_seconds','max_wait_seconds')]==[nw[k] for k in ('preDelay','postDelay','maxTimeWaitingForNextWave')]
  assert len(w['fragments'])==len(nw['fragments']);n=0
  for fi,(nf,f) in enumerate(zip(nw['fragments'],w['fragments'])):
   assert f['pre_delay_seconds']==nf['preDelay'];cursor=0
   for ai,na in enumerate(nf['actions']):
    actions+=1
    for ri in range(na['count']):
     a=f['actions'][cursor];cursor+=1;assert a['delay_seconds']==na['preDelay']+ri*na['interval'] and a['count']==1 and a['interval_seconds']==na['interval']
     if na['actionType']=='SPAWN':
      assert a['managed']==na['managedByScheduler'] and a['blocks_wave']==(not na['dontBlockWave']) and a['blocks_fragment']==na['blockFragment']
      spawn=a['spawn'];assert spawn['definition']=='unit/'+na['key'];population[spawn['definition']]+=1;n+=1
      route=deepcopy(native['routes'][na['routeIndex']]);route['motionMode']='WALK'
      for key in ('startPosition','endPosition'):route[key]['row']=rows-1-route[key]['row']
      offset=False
      for ci,c in enumerate(route.get('checkpoints') or []):
       c['position']['row']=rows-1-c['position']['row'];offset=offset or any(c['reachOffset'].values());assert not c['randomizeReachOffset'] and c['reachDistance']==0
       assert c['type'] in ('MOVE','WAIT_CURRENT_FRAGMENT_TIME')
       if c['type']=='WAIT_CURRENT_FRAGMENT_TIME':assert c['time']==30;special.append({'route':na['routeIndex'],'wave':wi,'fragment':fi,'checkpoint':ci,'consumer':'captured fragment_start + quantize30'})
      if offset:
       route['reach_offset_policy']={'rule':'rule/m9_checkpoint_cartesian','parameters':{'axis_signs':{'row':-1,'col':1}}};special.append({'route':na['routeIndex'],'target':{'row':3.56,'col':6.44}})
      assert spawn['route']==route and spawn['position']==route['startPosition']
      assert spawn['placement']=={'rule':'rule/m7_spawn_rectangle','stream':'spawn','sample_axes':['col','row'],'sample_zero_range':False,'random_range':{'row':route['spawnRandomRange']['y'],'col':route['spawnRandomRange']['x']},'offset':{'row':-route['spawnOffset']['y'],'col':route['spawnOffset']['x']}}
      assert spawn['parameters']=={'native_wave':wi,'native_fragment':fi,'native_route_index':na['routeIndex'],'native_action':ai,'native_repeat':ri}
     else:
      assert a['kind']=='effects' and a['managed'] is False and a['blocks_wave'] is False and a['blocks_fragment'] is False
      assert a['metadata']['native_action']==na and a['metadata']['completion_policy']=='synchronous_headless_ack';ui.append(a)
   assert cursor==len(f['actions'])
  wavecounts.append(n)
 assert wavecounts==[6,9,22] and sum(population.values())==37 and actions==22 and len(special)==7 and len(ui)==3
 # Raw Unity re-read; use offline private BE reader, never author assertions.
 cache={}
 def objects(p):
  p=(ROOT.parent/p).resolve()
  if p not in cache:cache[p]={x.path_id:x for x in UnityPy.load(str(p)).objects}
  return cache[p]
 db=read('../unpack_work/campaign_tables/enemy_database.json');enemyresults=[];reader=library_identity();byid={x['id']:x for x in model['entities']}
 for e in source['enemies']:
  cid=e['native_id'];rr=e['resolved_native'];assert rr['raw_rows']==[r for r in db[cid] if r['level']<=rr['native_level']]
  resolved={}
  for row in db[cid]:
   if row['level']>rr['native_level']:continue
   for k,v in row['enemyData'].items():
    if k=='attributes':
     for kk,vv in v.items():
      if vv['m_defined']:resolved.setdefault('attributes',{})[kk]=vv['m_value']
    elif isinstance(v,dict) and v.get('m_defined'):resolved[k]=v['m_value']
  assert all(resolved[k]==v for k,v in rr['resolved'].items() if k!='attributes')
  assert all(resolved['attributes'][k]==v for k,v in rr['resolved']['attributes'].items())
  pf=e['prefab'];objs=objects(pf['source']);assert sha(ROOT.parent/pf['source'])==pf['source_sha256'];combat=objs[pf['combat_path_id']].read_typetree();mode=objs[pf['mode_path_id']].read_typetree();assert combat==pf['combat_fields'] and mode['_combat']['m_PathID']==pf['combat_path_id'] and mode['_attack']==pf['raw_mode_attack_pointer']
  anim=e['animation'];ao=objects(anim['source']['path']);wrapper=ao[anim['textasset_path_id']].get_raw_data();payload=unity_payload(wrapper);assert hashlib.sha256(wrapper).hexdigest()==anim['wrapper_sha256'] and hashlib.sha256(payload).hexdigest()==anim['payload_sha256'];parsed=parse_spine(payload);assert parsed==anim['parsed']
  animator=objects(anim['animator']['source']['path'])[anim['animator']['path_id']].read_typetree();assert {k:v for k,v in animator.items() if k.startswith('_')}==anim['animator']['fields']
  binding=resolve_animation(combat['_animKey'],animator['_animations'],parsed);assert binding==e['exact_attack_binding'];hits=[x for x in binding['events'] if x['name']=='OnAttack'];ability=next(x for x in model['abilities'] if x['id']==f'ability/{cid}/normal_attack');assert ability['timeline']==[{'at_seconds':x['seconds'],'effect':{'op':'damage','scale':combat['_atkScale'],'damage_type':{1:'physical',2:'arts',3:'true'}[combat['_damageType']]}} for x in hits]
  b=byid['unit/'+cid]['components']['attributes']['base'];attrs=resolved['attributes']
  for nk,mk in {'maxHp':'max_hp','atk':'atk','def':'def','magicResistance':'mres','baseAttackTime':'attack_interval','moveSpeed':'move_speed','massLevel':'mass_level'}.items():assert b[mk]==attrs[nk]
  assert b['attack_speed_ratio']==attrs['attackSpeed']/100
  mover=anim['root_mover_components'][0];mt=objs[mover['path_id']].read_typetree();assert {k:v for k,v in mt.items() if k.startswith('_')}==mover['fields']
  assert byid['unit/'+cid]['components']['spatial']['steering']['parameters']=={'response_factor':mt['_steeringFactor'],'max_acceleration':mt['_maxSteeringForce'],'arrival_radius':.05}
  enemyresults.append({'enemy':cid,'mode_path_id':pf['mode_path_id'],'combat_path_id':pf['combat_path_id'],'actual_PPtr_and_typetree_equal':True,'OnAttack_frames':[x['frame'] for x in hits]})
 assert library_identity()==reader==source['spine_reader_identity'] and len(enemyresults)==6
 probe=ui_probe(ui);route_runtime=route_probe(model)
 full=read('validation/campaign/m12_primary_00_11_full_20261002.json');assert full['passed'] and full['package_sha256']==PIN and full['checkpoint_resume_equal'] and full['replay_equal'] and full['state']['kills']==37 and full['state']['leaks']==0
 assert full['event_counts']['enemy.info_displayed']==2 and full['event_counts']['story.finished']==1 and full['event_counts']['timeline.action']==40 and full['event_counts']['timeline.member_released']==37
 assert implementation_digest()==CORE
 output={'schema':'ark-sim/00-11-independent-consumers/v1','passed':True,'subject_model_content_sha256':PIN,'implementation_sha256':CORE,'source_lock_count':len(audit['source_locks']),'runtime_module':sys.modules['ark_sim'].__file__,'native_actions':actions,'native_spawn_action_groups':actions-2,'wave_spawn_counts':wavecounts,'population':dict(population),'special_route_consumers':special,'raw_actual_enemy_consumers':enemyresults,'synchronous_UI_probes':probe,'native_route_runtime_probe':route_runtime,'full_run_scope':'Existing independently locked same-subject37/0 full CP/replay checked; not reexecuted here','zero_lifetime_policy':'native managed flags retained; logical effects completion is model ACK via actual timeline.action after processed effect, not native callback','tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(Path(__file__).relative_to(ROOT)),'result':'passed'}]}
 write('validation/campaign/00_11_source_consumer_subchecks.json',output);print(json.dumps({'passed':True,'waves':wavecounts,'enemies':len(enemyresults),'specials':len(special),'UI':len(ui)}))
if __name__=='__main__':run()
