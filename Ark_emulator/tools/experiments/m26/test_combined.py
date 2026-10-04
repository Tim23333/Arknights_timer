"""Decision target discovery and actual selection share live qualification."""
from copy import deepcopy
import pytest

from tools.experiments.m26.test_decisions import fixture, make, cp
from tools.experiments.m26.test_eligibility import DEFAULTS, RAW


def combined(flag=2):
    p = fixture()
    p['entities'][0]['components']['selection_state'] = {'side':1}
    p['entities'][1]['components']['selection_state'] = {'side':0}
    p['selectors'][0]['eligibility'] = {'rule':'rule/eligibility', 'parameters':{
        'source_configuration':deepcopy(RAW), 'side_policy':'relative_ally_enemy',
        'neutral_policy':'reject', 'defaults':deepcopy(DEFAULTS)}}
    p['selectors'][0].update(ordering='random', parameters={'random_stream':'imp'})
    p['rules'] = [{'id':'rule/eligibility','kind':'rule','contract':'targeting.eligibility',
                   'implementation':{'type':'provider','provider':'model.targeting.eligibility'}}]
    p['buffs'] = [{'id':'buff/free','kind':'buff','duration_seconds':1/30,
                   'selection_flags':{'abnormal_flags':[flag]}}]
    p['abilities'].append({'id':'ability/free','kind':'ability','activation':{'mode':'manual',
        'on_start':[{'op':'apply_buff','buff':'buff/free','target':'source'}]},'timeline':[]})
    p['entities'][1]['components']['abilities'].append('ability/free')
    return p


@pytest.mark.parametrize('flag', [2,17])
def test_public_buff_blocks_target_discovery_and_packet_until_half_open_expiry(flag):
    s = make(combined(flag)); s.submit({'action':'skill','source':'target','ability':'ability/free'}, at=0)
    initial_rng = s.session.random.snapshot(); s.advance(1)
    assert s.ctx.get('enemy', ('spatial','position'))['col'] == pytest.approx(.1)
    assert not [e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==2]
    assert s.session.random.snapshot() == initial_rng
    before = s.checkpoint()
    assert s.ctx.spatial.eligible('enemy','selector/enemies') == [3]
    assert s.checkpoint() == before
    s.advance(1)
    assert s.ctx.get('enemy', ('spatial','position'))['col'] == pytest.approx(.1)
    assert len([e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==2]) == 1
    assert s.session.random.snapshot() != initial_rng
    s.advance(6); assert s.ctx.resources.current('target','hp') == 80
    cp(s)


def test_pure_eligibility_and_actual_select_have_identical_filtered_identity():
    p = combined(); p['entities'][1]['components']['selection_state']['target_free'] = True
    s = make(p); before = s.checkpoint()
    assert s.ctx.spatial.eligible('enemy','selector/enemies') == []
    assert s.checkpoint() == before
    rng = s.session.random.snapshot(); assert s.ctx.spatial.select('enemy','selector/enemies') == []
    assert s.session.random.snapshot() == rng
    # select emits trace events and is not a public replay command. Use a fresh
    # identical simulation for the full public-command replay assertion.
    s = make(p)
    s.advance(3); assert s.ctx.get('enemy', ('spatial','position'))['col'] == pytest.approx(.3)
    assert s.ctx.resources.current('target','hp') == 100
    cp(s)


def test_qualification_rule_failure_rolls_back_complete_action():
    p = combined(); p['rules'][0]['implementation'] = {'type':'expression','expression':'1/0'}
    s = make(p); before = s.checkpoint()
    with pytest.raises(Exception, match='zero|division'):
        with s.session.atomic():
            s.ctx.resources.adjust('enemy','hp',-1)
            s.ctx.behavior.plan('enemy')
    assert s.checkpoint() == before
