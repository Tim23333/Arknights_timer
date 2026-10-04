"""Read-only bounded progress evidence; no computation/event side effects."""
from ark_sim.contracts import thaw


def summarize(sim):
    enemies=[]
    for entity in sim.session.world.entities():
        if 'enemy' not in entity['tags'] or not sim.ctx.alive(entity['id']):continue
        components=entity['components'];runtime=components.get('runtime',{});spatial=components.get('spatial',{})
        enemies.append({'id':entity['id'],'definition':entity['definition_id'],'active':sim.ctx.active(entity['id']),
            'resources':{key:data['current'] for key,data in components.get('resources',{}).items()},
            'position':thaw(spatial.get('position')),'route_state':thaw(spatial.get('route_state')),
            'route_cursor':spatial.get('route_cursor'),'route_hidden':spatial.get('route_hidden',False),
            'blocked_by':runtime.get('blocked_by'),'behavior_decision':thaw(runtime.get('behavior_decision')),
            'casts':[{key:cast.get(key) for key in ('id','ability','started_at','ends_at')} for cast in runtime.get('casts',{}).values()]})
    state=sim.ctx.state()
    return {'schema':'ark-sim/run-progress-diagnostic/v1','tick':sim.session.time,'event_count':len(sim.session.events),
        'kills':state['kills'],'leaks':state['leaks'],'pending':state['pending_waves'],'finished':state['finished'],
        'alive_enemies':enemies,'pending_tasks':len(sim.session.scheduler.pending),
        'timeline':thaw(state.get('timeline',{})),'source_scope':'bounded live read; no actual-game accuracy claim'}
