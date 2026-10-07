"""Replaceable mathematical profiles; no native steering/body claims."""
import math

def trajectory(inputs,params,context):
 p={**params,**inputs['trajectory_parameters']};record=inputs['positions'][0];current=record['position'];start=record['start'];target=record['last_target'];mode=p['mode'];state=dict(record.get('motion_state',{}))
 if mode=='fixed':return {'position':dict(current),'reached':False,'motion_state':state}
 if mode=='follow':return {'position':dict(target),'reached':False,'motion_state':state}
 if mode!='homing':raise ValueError('unknown mathematical motion mode')
 speed=p['speed'];dt=p['delta_seconds'];distance=math.hypot(target['row']-current['row'],target['col']-current['col']);reached=distance<=speed*dt+p.get('arrival_tolerance',1e-12);step=distance if reached else min(distance,speed*dt);fraction=step/distance if distance else 0
 point={'row':current['row']+(target['row']-current['row'])*fraction,'col':current['col']+(target['col']-current['col'])*fraction}
 traveled=state.get('traveled',0)+step;length=state.get('launch_length',math.hypot(target['row']-start['row'],target['col']-start['col']));u=min(1,traveled/length) if length else 1
 if reached:point={'row':target['row'],'col':target['col']}
 point['height']=4*p.get('raise_height',0)*u*(1-u) if length>=p.get('height_threshold',0) else 0
 return {'position':point,'reached':reached,'motion_state':{'traveled':traveled,'launch_length':length}}

def collision(inputs,params,context):
 params={**params,**inputs['spatial_state'].get('parameters',{})}
 if not params.get('enabled',True):return {'hits':[],'terrain_hit':False,'stop':False}
 p=inputs['projectile'];a=p['previous_position'];b=p['position'];last=p['previous_target_position'];target=p['target_position'];hits=[]
 for entity in inputs['entities']:
  if entity['id']!=p['trace_target'] or not p['target_available']:continue
  r0=(a['row']-last['row'],a['col']-last['col']);rv=((b['row']-a['row'])-(target['row']-last['row']),(b['col']-a['col'])-(target['col']-last['col']))
  denom=rv[0]**2+rv[1]**2;t=max(0,min(1,-(r0[0]*rv[0]+r0[1]*rv[1])/denom)) if denom else 0
  if math.hypot(r0[0]+t*rv[0],r0[1]+t*rv[1])<=params.get('radius',0):hits.append(entity['id'])
 return {'hits':hits,'terrain_hit':False,'stop':False}
trajectory.version='projectile-planar-homing-parabola-v1'
collision.version='swept-relative-trace-point-v1'
