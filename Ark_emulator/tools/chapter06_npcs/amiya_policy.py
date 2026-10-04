"""Explicit replaceable two-stage source Amiya projectile profile."""
def trajectory(inputs,params,context):
    p={**params,**inputs['trajectory_parameters']};record=inputs['positions'][0]
    start=record['start'];target=record['last_target'];age=p['age_seconds'];duration=p['start_duration']+p['travel_duration']
    fraction=min(1,max(0,age/duration));point={'row':start['row']+(target['row']-start['row'])*fraction,
        'col':start['col']+(target['col']-start['col'])*fraction}
    return {'position':point,'reached':age>=duration,'motion_state':{'native_start_distance':p['start_distance'],'reference_fraction':fraction}}


def providers():
    from tools.chapter06_npcs.policies import providers as npc_providers
    return {**npc_providers(),'reference.c6.amiya_movement':{'callable':trajectory,'version':'1.0.0'}}
