import pytest
from ark_sim import Compiler,Engine


def fixture(flag=True):
    ability={'id':'ability/settle','kind':'ability','activation':{'mode':'manual','settle_blocking':flag},'timeline':[]}
    unit={'id':'unit/source','kind':'entity','components':{'abilities':['ability/settle']}}
    return {'definitions':[unit,ability],'scenarioDraft':{'id':'scene/settle','ruleset':'ruleset/ark_standard',
        'objectives':{},'initialEntities':[{'definition':'unit/source','instanceAlias':'source'}]}}


@pytest.mark.parametrize('flag',[0,1,'true',None,[]])
def test_settle_flag_strict_bool(flag):
    with pytest.raises(ValueError,match='strict boolean'):Compiler().compile(fixture(flag))


def test_failed_blocking_settlement_rolls_back_entire_ability_payment_rng_events():
    s=Engine.create(Compiler().compile(fixture()),seed=606);before=s.checkpoint()
    def fault():
        s.ctx.set('source',('runtime','marked'),True);s.session.random.sample('settle-fault')
        s.ctx.emit('settle.fault',{'source':2});raise ValueError('settlement failed')
    s.ctx.spatial.blocking=fault
    with pytest.raises(ValueError,match='settlement failed'):s.ctx.abilities.start('source','ability/settle')
    assert s.checkpoint()==before


def test_explicit_false_preserves_no_opt_selection_without_settlement():
    s=Engine.create(Compiler().compile(fixture(False)),seed=606)
    def fault():raise AssertionError('false must not reconcile')
    s.ctx.spatial.blocking=fault;s.ctx.abilities.start('source','ability/settle')
    assert len(s.ctx.get('source',('runtime','casts')))==1
