"""Independent raw-source mappings; never imports author builders or fixtures."""
import json,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exact(a,b):
 if type(a) is not type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 return a==b
def audit(stage_override=None,overlay_override=None):
 folder=ROOT/'packages/campaign/chapter08_stage_controls';source=read(folder/'source/story_opera.source.v1.json');module=read(folder/'controls.module.v1.json');frozen=read(folder/'source/source.freeze.v1.json');assert all(sha(Path(p))==h for p,h in frozen['pins'].items());script=(folder/'source/main_08-17.fixed56.txt').read_bytes();assert hashlib.sha256(script).hexdigest()==source['story']['fixed_payload_sha256'];assert script.decode('utf8')==source['story']['raw_utf8_script'];lines=script.decode('utf8').splitlines();assert 'is_autoable=false' in lines[0];popup=[line for line in lines if line.startswith('[PopupDialog(')];assert len(popup)==8
 story=module['controls'][0];acks=[s for s in story['steps'] if s['kind']=='ack'];assert [s['key'] for s in acks]==['popup/'+str(i) for i in range(8)] and story['ack_policy']=='external';observed=[e for s in story['steps'] if s['kind']=='effects' for e in s['effects'] if e['event']=='source.story.popup.observed'];assert [e['payload']['raw_command']['raw'] for e in observed]==popup;assert story['steps'][-1]=={'kind':'delay','seconds':.3}
 decoded=read(folder/'source/config_common.decoded.json');cfg=next(row for row in decoded['monos'] if row['raw'].get('m_Name')=='main_08-17');assert exact(cfg,source['opera']['config_object'])
 av={}
 for raw in cfg['raw']['_commands']:
  key=raw['key']
  if key not in ('blast_effect_x','blast_effect_y'):continue
  nodes=json.loads(raw['operaNodes']['SerializedState']);assert raw['operaNodes']['SerializedObjectReferences']==[];assert exact(nodes,source['opera']['commands'][key]['parsed_nodes']);control=next(c for c in module['controls'] if c['id'].endswith('/'+key));pos=0;actual=[]
  for step in control['steps']:
   if step['kind']=='delay':pos+=step['seconds']
   else:
    for e in step['effects']:actual.append((round(pos,9),e['payload']['node_index'],e['payload']['source_node']))
  expected=sorted([(n['_preDelay'],i,n) for i,n in enumerate(nodes)],key=lambda row:(row[0],row[1]));assert actual==expected and pos==3;av[key]={'nodes':[n['$type'] for n in nodes],'offset_frames':[0,6,9],'completion_frames':90,'raw_parameters_exact':True}
 native=read(ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json')['stages']['level_main_08-17'];raw=native['native_document'];stage=stage_override if stage_override is not None else read(ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v2.json');scene=stage['scenarioDraft'];assert scene['map']['rows']==9 and scene['map']['cols']==15 and exact(scene['map']['tiles'],native['map_plan']['tiles']);assert scene['seed']==raw['randomSeed'];assert exact(scene['metadata']['native_options'],raw['options']);assert scene['resources']['dp']['initial']==15 and scene['resources']['dp']['capacity']==99 and scene['resources']['life']=={'initial':3,'capacity':3};assert scene['parameters']['deploy_capacity']==9;assert len(scene['roster'])==12
 waves=scene['timeline']['waves'];assert len(waves)==len(raw['waves'])==4;count=0;controls={};routes=0
 for wi,(w,nw) in enumerate(zip(waves,raw['waves'])):
  assert (w['pre_delay_seconds'],w['post_delay_seconds'],w['max_wait_seconds'])==(nw['preDelay'],nw['postDelay'],nw['maxTimeWaitingForNextWave']);assert len(w['fragments'])==len(nw['fragments'])
  for fi,(frag,nfrag) in enumerate(zip(w['fragments'],nw['fragments'])):
   assert frag['pre_delay_seconds']==nfrag['preDelay'] and len(frag['actions'])==len(nfrag['actions'])
   for ai,(a,na) in enumerate(zip(frag['actions'],nfrag['actions'])):
    assert exact(a['metadata']['native_action'],na);assert a['count']==na['count'] and a['delay_seconds']==na['preDelay'] and a['interval_seconds']==na['interval'];assert a['managed']==na['managedByScheduler'] and a['blocks_fragment']==na['blockFragment'] and a['blocks_wave']==(not na['dontBlockWave'])
    if na['actionType']=='SPAWN':
     count+=na['count'];expected=json.loads(json.dumps(raw['routes'][na['routeIndex']]));expected['startPosition']['row']=8-expected['startPosition']['row'];expected['endPosition']['row']=8-expected['endPosition']['row'];
     for point in expected.get('checkpoints') or []:point['position']['row']=8-point['position']['row']
     actual={k:v for k,v in a['spawn']['route'].items() if k not in ('transition_policy','reach_offset_policy')};assert exact(actual,expected);routes+=1
    else:controls[na['actionType']]=controls.get(na['actionType'],0)+na['count']
 assert count==44 and controls['STORY']==1 and controls['PLAY_OPERA']==17
 overlay=overlay_override if overlay_override is not None else read(ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v2.life99999.v1.json');overlay['scenarioDraft']['resources']['life']={'initial':3,'capacity':3}
 for container,original in [(overlay['manifest']['metadata'],stage['manifest']['metadata']),(overlay['scenarioDraft']['metadata'],scene['metadata'])]:
  for key in set(container)-set(original):container.pop(key)
 assert exact(overlay,stage)
 units={d['id']:d for d in stage['definitions'] if d['kind']=='entity'};boss=units['unit/ch8/bsnake/cadb87696bef4de2'];assert boss['components']['attributes']['base']['max_hp']==50000 and boss['components']['attributes']['base']['atk']==770;assert boss['components']['resources']['hp']['initial']==50000;normal=[d for d in stage['definitions'] if d['id'].startswith('ability/ch8/bsnake/normal/phase')];assert len(normal)==2 and all(d['duration_seconds']==2.3333332538604736 and d['timeline'][0]['at_seconds']==1.0333333015441895 for d in normal);restore=next(d for d in stage['definitions'] if d['id']=='rule/ch8/bsnake/first_restore');assert restore['implementation']['expression']=='inputs.parameters.capacity if context.rebirth.count == 1 else 0'
 return {'story_popup_raw_exact':8,'source_pin_count':len(frozen['pins']),'opera':av,'native_births':count,'all_action_fields_exact':True,'original_route_copies_exact':routes,'controls_by_native_type':controls,'native_DP':15,'native_life':3,'slots':9,'fixed_roster_count':12,'lifeonly_restoration_type_exact':True,'restore_policy':'Newcontent first_restore capacity(full75k after+.5HP), unlike historicalliteral .5. This independent fieldaudit records chosenpolicy and preserves oldgeneric37500 proofs; no native methodbody/clientcorrectness inferred.'}
if __name__=='__main__':print(json.dumps(audit(),ensure_ascii=False))
