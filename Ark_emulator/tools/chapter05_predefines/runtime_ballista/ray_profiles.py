"""Generic cardinal map-bound rays and first qualified swept-circle collisions."""
import math
from collections.abc import Mapping
from ark_sim.contracts import thaw
from ark_sim.domains.selection import validate_eligibility,validate_state
DIRECTIONS={'right':(0,1),'left':(0,-1),'down':(1,0),'up':(-1,0)}
def trajectory(inputs,params,context):
 p={**thaw(params),**thaw(inputs['trajectory_parameters'])};record=inputs['positions'][0];state=thaw(record.get('motion_state',{}));start=record['start'];bounds=context.get('projectile_map_bounds')
 if not isinstance(bounds,Mapping) or set(bounds)!={'min_row','max_row','min_col','max_col'}:raise ValueError('directional ray requires actual map bounds projection')
 speed=p['speed']
 if type(speed) not in (int,float) or not math.isfinite(speed) or speed<=0:raise ValueError('directional ray speed must be finite positive')
 if p.get('extent_policy')!='map_bounds':raise ValueError('directional ray extent policy must be explicit map_bounds')
 if not state:
  face=inputs['source']['components']['spatial'].get('facing')
  if face not in DIRECTIONS:raise ValueError('directional ray requires cardinal source facing')
  dr,dc=DIRECTIONS[face];length=(bounds['max_row']-start['row']) if dr>0 else (start['row']-bounds['min_row']) if dr<0 else (bounds['max_col']-start['col']) if dc>0 else (start['col']-bounds['min_col']);state={'direction':[dr,dc],'length':max(0,length),'traveled':0,'launch_facing':face}
 dr,dc=state['direction'];state['traveled']=min(state['length'],state['traveled']+speed*p['delta_seconds']);point={'row':start['row']+dr*state['traveled'],'col':start['col']+dc*state['traveled']}
 if 'height' in start:point['height']=start['height']
 return {'position':point,'reached':state['traveled']>=state['length'],'motion_state':state}
def collision(inputs,params,context):
 p={**thaw(params),**thaw(inputs['spatial_state'].get('parameters',{}))};eligibility=p.get('eligibility');validate_eligibility(eligibility,'qualified ray collision eligibility');projection=context.get('projectile_selection_states');previous=context.get('projectile_candidate_previous_positions',{})
 if not isinstance(projection,Mapping) or set(projection)!={'source','candidates'}:raise ValueError('qualified ray collision requires effective selection projections')
 validate_state(projection['source'],complete=True);radius=p['radius']
 if type(radius) not in (int,float) or not math.isfinite(radius) or radius<0:raise ValueError('qualified ray radius must be nonnegative finite')
 packet=inputs['projectile'];a=packet['previous_position'];b=packet['position'];contacts=[]
 for entity in inputs['entities']:
  if entity['id']==context['source']['id'] and p.get('exclude_source',False):continue
  key=str(entity['id']);target=entity['components']['spatial']['position'];last=previous.get(key,target);state=projection['candidates'].get(key)
  if state is None:raise ValueError('qualified ray candidate projection absent')
  validate_state(state,complete=True);decision=context.calculate('targeting.eligibility',{'source':context['source'],'candidate':entity,'selector':{'healing':False},'parameters':eligibility['parameters'],'selection_states':{'source':projection['source'],'candidate':state}},rule_id=eligibility['rule']).value
  if not isinstance(decision,Mapping) or type(decision.get('accepted')) is not bool:raise ValueError('qualified ray eligibility must return a strict decision')
  if not decision['accepted']:continue
  # Earliest entry, not nearest endpoint; relative motion preserves a mover
  # crossing the ray inside this real logic tick. Ties have stable actor order.
  q=(a['row']-last['row'],a['col']-last['col']);v=((b['row']-a['row'])-(target['row']-last['row']),(b['col']-a['col'])-(target['col']-last['col']));rr=radius+entity['components']['spatial'].get('radius',0);aa=v[0]**2+v[1]**2;bb=2*(q[0]*v[0]+q[1]*v[1]);cc=q[0]**2+q[1]**2-rr**2
  if cc<=0:t=0
  elif aa==0:continue
  else:
   disc=bb*bb-4*aa*cc
   if disc<0:continue
   t=(-bb-math.sqrt(disc))/(2*aa)
   if not 0<=t<=1:continue
  contacts.append((t,entity['id']))
 contacts.sort();return {'hits':[x[1] for x in contacts],'terrain_hit':False,'stop':False}
trajectory.version='cardinal-fixedlaunch-mapbound-ray-v1'
collision.version='qualified-relative-swept-firstentry-circle-v1'
