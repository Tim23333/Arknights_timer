"""First full28s source screen keeps ten volleys, then source15s invincibility."""
import json
from copy import deepcopy
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_bsnake.screen_policy_v1 import providers
from tools.chapter08_joint_v4.build_screen_native_rows_v1 import OUT, build; from tools.chapter08_joint_v4.build_first_screen_v1 import SCREEN, INVINCIBLE
from tools.campaign_ordered_checkpoint import write_ordered, load_bound


def package():
    p = json.loads(OUT.read_bytes())
    p['entities'].append({'id': 'unit/firstscreen/director', 'kind': 'entity',
                          'components': {'spatial': {}, 'abilities': ['ability/firstscreen/kill']}})
    p['abilities'].append({'id': 'ability/firstscreen/kill', 'kind': 'ability',
                           'activation': {'mode': 'manual', 'on_start': [
                               {'op': 'instant_kill', 'target': 2, 'parameters': {'cause': 'source_firstscreen', 'skip_rebirth': False}}]},
                           'timeline': []})
    p['entities'].append({'id': 'unit/firstscreen/recipient', 'kind': 'entity', 'tags': ['player'],
                          'components': {'attributes': {'base': {'max_hp': 100000, 'atk': 0, 'def': 913, 'mres': 40}},
                                         'resources': {'hp': {'initial': 100000, 'capacity': 100000, 'role': 'health'}},
                                         'selection_state': {'side': 0, 'motion': 1, 'category': 1, 'unit_type': 1},
                                         'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    p['scenarioDraft'] = {'id': 'scene/firstscreen/source', 'ruleset': 'ruleset/ark_standard',
                          'map': {'rows': 9, 'cols': 15}, 'objectives': {}, 'initialEntities': [
                              {'definition': p['entities'][0]['id'], 'instanceAlias': 'boss', 'position': {'row': 2, 'col': 6}},
                              {'definition': 'unit/firstscreen/director', 'instanceAlias': 'director', 'position': {'row': 0, 'col': 0}},
                              *[{'definition': 'unit/firstscreen/recipient', 'instanceAlias': 'recipient' + str(row),
                                 'position': {'row': row, 'col': 3}} for row in (1, 2, 3, 4, 5, 6, 7)]]}
    return p


def test_exact_source_content_rebuild():
    assert json.loads(OUT.read_bytes()) == build()


def test_realHP0_5s_restore_full28screen10x2_then15invincible_CP400_head(tmp_path):
    p = package()
    reg = providers()
    program = Compiler(providers=reg).compile(p)
    s = Engine.create(program, providers=reg, seed=81843)
    s.submit({'action': 'skill', 'source': 'director', 'ability': 'ability/firstscreen/kill'}, at=1)
    s.advance(151)
    assert s.ctx.resources.current('boss', 'hp') == 0 and not s.ctx.active('boss')
    s.advance(1)
    assert s.ctx.resources.current('boss', 'hp') == 37500 and s.ctx.active('boss')
    assert s.ctx.resources.current('boss', 'mode') == 2
    assert s.ctx.buffs.controls('boss')['move'] is False and s.ctx.buffs.controls('boss')['block'] is False
    s.advance(248)
    f = tmp_path / 'screen400.cp.json'
    pin = write_ordered(f, s.checkpoint())
    r = Engine.restore(program, load_bound(f, pin), providers=reg)
    s.advance(1042)
    r.advance(1042)
    h = replay(program, s.export_replay(), providers=reg)
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    volleys = [event['time'] for event in s.session.events if event['type'] == 'source.bsnake.screen.volley']
    assert volleys == list(range(211, 752, 60))
    assert len([event for event in s.session.events if event['type'] == 'projectile.launched']) == 70
    hits = [event for event in s.session.events if event['type'] == 'damage.accepted']
    assert len(hits) == 70 and all(event['payload']['amount'] == 693 for event in hits)
    assert s.ctx.resources.current('boss', 'hp') == 37500 and s.ctx.resources.current('boss', 'mode') == 1
    assert all(s.ctx.buffs.controls('boss').values())
    removed = [(event['time'], event['payload']['buff']) for event in s.session.events if event['type'] == 'buff.removed']
    assert (991, SCREEN) in removed and (1441, INVINCIBLE) in removed
    assert len([event for event in s.session.events if event['type'] == 'source.bsnake.hint.requested']) == 1
