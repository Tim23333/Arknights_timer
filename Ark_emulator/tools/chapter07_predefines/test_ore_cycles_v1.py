"""Repeated source pulses consume actual SP and preserve one packet per unit."""
from tools.chapter07_predefines.test_ore_v1 import make


def test_second_pulse_is_not_lost_to_a_permanent_payload_marker():
    simulation = make()
    simulation.advance(480)
    starts = [e['time'] for e in simulation.session.events if e['type'] == 'ability.started']
    packets = [e for e in simulation.session.events if e['type'] == 'damage.accepted']
    assert starts == [210, 451]
    assert [e['time'] for e in packets] == [229, 229, 229, 470, 470, 470]
    assert simulation.ctx.resources.current('ally', 'hp') == 4000
    assert simulation.ctx.resources.current('enemy', 'hp') == 4000
    assert simulation.ctx.resources.current('immune', 'hp') == 5000
    assert simulation.ctx.resources.current('listener', 'hp') == 4000
    assert simulation.ctx.resources.current('ore', 'sp') == 0
