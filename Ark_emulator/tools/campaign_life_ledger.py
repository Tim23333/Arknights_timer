"""Audit actual leak-loss calculations separately from leaked actor counts."""
def ledger(sim,life_resource):
    losses=[];exits=[]
    for event in sim.session.events:
        if event['type']=='calculation' and event['payload']['calculation_id']=='lifecycle.leak_loss':
            value=event['payload']['value']
            if type(value) not in (int,float) or value<0:raise ValueError('Leak-loss output must be nonnegative numeric')
            losses.append({'event_id':event['id'],'tick':event['time'],'loss':value})
        elif event['type']=='entity.exited':
            exits.append({'event_id':event['id'],'tick':event['time'],'target':event['payload']['target']})
    spec=sim.program.scenario['resources'][life_resource];initial=spec['initial']
    final=sim.ctx.resources.current('system/battle',life_resource);total=sum(row['loss'] for row in losses)
    return {'schema':'ark-sim/base-life-ledger/v1','initial':initial,'final':final,
        'total_calculated_leak_loss':total,'leaked_entity_count':sim.ctx.state()['leaks'],
        'leak_calculations':losses,'leaked_events':exits,
        'calculation_exit_count_equal':len(losses)==len(exits)==sim.ctx.state()['leaks'],
        'only_leak_loss_balance_equal':initial-total==final,
        'scope':'Declared life resource balance if it has no other recovery/cost effects; actual leak-loss event outputs retained',
        'actual_client_verified':False}
