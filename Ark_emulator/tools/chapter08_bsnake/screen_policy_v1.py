"""Pure screen-row trajectory; same source actor, no world/HP/position mutations."""
from ark_sim.contracts import thaw

def screen_ray(inputs,params,context):
 p={**thaw(params),**thaw(inputs['trajectory_parameters'])};state=thaw(inputs['positions'][0].get('motion_state',{}));b=context['projectile_map_bounds']
 if not state:
  row=p['row'];col=b['min_col']+.5+p['border'];end=b['max_col']-.5-p['border'];state={'origin':{'row':row,'col':col,'height':p['height']},'length':max(0,end-col),'traveled':0,'delay':p['delay_seconds']}
 age=p['age_seconds'];before=max(0,age-p['delta_seconds']-state['delay']);after=max(0,age-state['delay']);state['traveled']=min(state['length'],state['traveled']+p['speed']*(after-before));point={**state['origin'],'col':state['origin']['col']+state['traveled']};return {'position':point,'motion_state':state,'reached':state['traveled']>=state['length']}

def providers():
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 return {**BUILTIN_PROVIDERS,'reference.bsnake.screen_row':{'callable':screen_ray,'version':'1'}}
