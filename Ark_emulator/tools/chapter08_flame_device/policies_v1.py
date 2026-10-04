"""Pure four direction ray paths and fixed arts payload, no castermutation."""
from ark_sim.contracts import thaw
DIRECTIONS={'up':(-1,0),'right':(0,1),'down':(1,0),'left':(0,-1)}

def trajectory(inputs,params,context):
    p={**thaw(params),**thaw(inputs['trajectory_parameters'])};record=inputs['positions'][0];state=thaw(record.get('motion_state',{}));start=record['start'];bounds=context['projectile_map_bounds']
    if not state:
        dr,dc=DIRECTIONS[p['direction']]
        length=bounds['max_row']-start['row'] if dr>0 else start['row']-bounds['min_row'] if dr<0 else bounds['max_col']-start['col'] if dc>0 else start['col']-bounds['min_col']
        state={'direction':[dr,dc],'length':max(0,length),'traveled':0}
    state['traveled']=min(state['length'],state['traveled']+p['speed']*p['delta_seconds']);dr,dc=state['direction']
    return {'position':{'row':start['row']+dr*state['traveled'],'col':start['col']+dc*state['traveled']},'reached':state['traveled']>=state['length'],'motion_state':state}

def fixed_arts(inputs,params,context):
    request=inputs['effect'];res=request['resistance'];amount=params['damage']*max(params['minimum_ratio'],1-res/100)
    return {'accepted':True,'amount':amount,'allocations':[],'events':[]}

def providers():
    from tools.chapter08_buff_lifetime.talula_providers_v1 import providers as source
    return {**source(),'reference.c8.flame.ray':{'callable':trajectory,'version':'1'},'reference.c8.flame.fixed_arts':{'callable':fixed_arts,'version':'1'}}
