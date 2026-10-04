"""Owned callback generations, fault rollback and frozen timer behavior."""
from copy import deepcopy
import pytest
from tools.chapter08_buff_lifetime.test_clock_v1 import package,providers
from ark_sim import Compiler,Engine


def test_runtime_refresh_retains_nominal_value_and_replaces_owned_task_only():
    p=package();reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.ctx.buffs.apply('owner','owner','buff/timer');s.advance(2)
    old=s.ctx.get('owner',('buffs','instances'))[0];s.ctx.buffs.apply('owner','owner','buff/timer');new=s.ctx.get('owner',('buffs','instances'))[0]
    assert new['id']==old['id'] and new['generation']==old['generation']+1 and new['lifetime_clock']['remaining_seconds']==30.5
    assert old['tasks']['lifetime'] not in {t['id'] for t in s.session.scheduler.pending}
    before=s.checkpoint();s.ctx.buffs.lifetime(s.session,{'target':old['target'],'instance':old['id'],'generation':old['generation']});assert s.checkpoint()==before


def test_late_rate_failure_rolls_back_actual_tick_world_tasks_and_remaining():
    p=package();p['rules'][0]['implementation']={'type':'provider','provider':'test/fault'}
    def fault(inputs,params,context):
        if context['time']>=2:raise ValueError('ratefault')
        return 1
    reg={**providers(),'test/fault':{'callable':fault,'version':'1'}};s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.ctx.buffs.apply('owner','owner','buff/timer');s.advance(2);old=s.ctx.get('owner',('buffs','instances'))[0]
    with pytest.raises(Exception,match='ratefault'):s.advance(1)
    current=s.ctx.get('owner',('buffs','instances'))[0]
    assert current['lifetime_clock']==old['lifetime_clock'] and current['generation']==old['generation']


def test_expiry_remove_callback_failure_retains_clock_and_modifiers():
    p=package();p['buffs'][0]['duration_seconds']=2/30;p['buffs'][0]['on_remove']=[{'op':'modify_resource','resource':'absent','delta':1}]
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.ctx.buffs.apply('owner','owner','buff/timer');s.advance(2);old=s.ctx.get('owner',('buffs','instances'))[0]
    with pytest.raises(ValueError):s.advance(1)
    assert s.ctx.get('owner',('buffs','instances'))[0]['lifetime_clock']==old['lifetime_clock']
    assert s.ctx.attributes.value('owner','atk')==110


def test_zero_rate_pauses_then_positive_resumes_without_forced_removal():
    p=package();p['rules'][0]['implementation']={'type':'expression','expression':'0 if context.time < 30 else 1'}
    p['buffs'][0]['duration_seconds']=1
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.ctx.buffs.apply('owner','owner','buff/timer');s.advance(60)
    assert s.ctx.get('owner',('buffs','instances'))
    s.advance(1);assert not s.ctx.get('owner',('buffs','instances'))


def test_malformed_lifetime_fields_preflight():
    p=package();p['buffs'][0]['lifetime']['count_when_inactive']=1
    with pytest.raises(ValueError):Compiler(providers=providers()).compile(p)


def test_samebuff_periodic_packet_excludes_exact_nominal_expiry_boundary():
    p=package();p['buffs'][0]['duration_seconds']=1;p['buffs'][0]['interval_seconds']=1
    p['buffs'][0]['effects']=[{'op':'emit','event':'should_not_periodic_at_expiry'}]
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.ctx.buffs.apply('owner','owner','buff/timer');s.advance(31)
    assert [e['time'] for e in s.session.events if e['type']=='buff.removed']==[30]
    assert not [e for e in s.session.events if e['type']=='should_not_periodic_at_expiry']
