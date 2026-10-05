"""Source input-target obstacle combat, with strict current-blocker identity."""


def blocker(inputs,params,context):
    from ark_sim.domains.selection import eligibility_profile
    source=inputs['source'];target=inputs['candidate'];current=source['components'].get('runtime',{}).get('blocked_by')
    if current is None or target['id']!=current:return {'accepted':False,'reason':'not_actual_blocker'}
    ss=inputs['selection_states']['source'];ts=inputs['selection_states']['candidate']
    if ts['category']==4 and ss['side']==1 and ts['side']==0:
        return {'accepted':True,'reason':'actual_input_obstacle_reference'}
    return eligibility_profile(inputs,{},context)


def providers():
    from tools.chapter09_stage919_assembly_v1.providers import providers as base
    return {**base(),'reference.ch9.finale_blocker':{'callable':blocker,'version':'strict-input-obstacle-v1'}}
