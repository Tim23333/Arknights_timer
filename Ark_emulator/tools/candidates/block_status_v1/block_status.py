"""Typed source BlockFree status gate with replaceable base blocking policy."""
from collections.abc import Mapping
from ark_sim.contracts import thaw
from .selection import validate_state,DEFAULT_STATE


def status_blocking(inputs,params,context):
    status=inputs['states'].get('target_selection')
    if status is None:raise ValueError('blocking status policy requires actual projected target selection')
    validate_state(status,complete=True)
    index=params.get('block_free_flag')
    if type(index) is not int or not 0<=index<46:raise ValueError('known typed BlockFree flag required')
    if index in status['abnormal_flags']:return {'accepted':False,'reason':'declared_block_free_status'}
    base=params.get('base_rule')
    if not isinstance(base,str) or not base:raise ValueError('explicit base blocking rule required')
    value=context.calculate('blocking.eligibility',thaw(inputs),rule_id=base).value
    if not isinstance(value,Mapping) or set(value)!={'accepted','reason'} or type(value['accepted']) is not bool or not isinstance(value['reason'],str):
        raise ValueError('base blocking policy must return typed decision')
    return thaw(value)


status_blocking.version='projected-status-blocking-v1'
