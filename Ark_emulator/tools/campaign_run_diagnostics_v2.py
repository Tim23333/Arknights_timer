"""Read actual movement substate, without changing frozen live diagnostics."""
from ark_sim.contracts import thaw
from tools.campaign_run_diagnostics import summarize as original


def summarize(sim):
    result=original(sim);result['schema']='ark-sim/run-progress-diagnostic/v2'
    for row in result['alive_enemies']:
        entity=sim.session.world.resolve(row['id']);spatial=sim.ctx.get(entity,('spatial',),{})
        movement=spatial.get('movement',{})
        row['route_state']=thaw(movement)
        row['route_cursor']=movement.get('checkpoint')
        row['velocity']=thaw(spatial.get('velocity'))
        row['forced_motion']=thaw(spatial.get('forced_motion'))
        checkpoints=(spatial.get('route') or {}).get('checkpoints') or []
        cursor=movement.get('checkpoint',0)
        row['next_checkpoint']=thaw(checkpoints[cursor]) if cursor<len(checkpoints) else None
    return result
