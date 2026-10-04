"""Source-native deck controls and explicitly selected fixed12 test override."""
import json
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_chapter01_roster_policy import native_deployment_fixture, apply_fixed12_overlay, INPUT, source_cards


def roundtrip(sim):
    restored = Engine.restore(sim.program, sim.checkpoint()); sim.advance(2); restored.advance(2)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(restored.session.events)) is None
    replayed = replay(sim.program, sim.export_replay())
    assert first_difference(sim.snapshot(), replayed.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(replayed.session.events)) is None


def test_native_source_cards_are_selected_with_actual_cost_and_capacity_limit():
    p = native_deployment_fixture(); stage, native = source_cards()
    assert [e['metadata']['native_card'] for e in p['entities']] == native
    assert len(p['scenarioDraft']['roster']) == 12 and p['scenarioDraft']['parameters']['deploy_capacity'] == 8
    assert all(e['metadata']['config']['level'] == 20 for e in p['entities'])
    # Independent source cost endpoints at this native level/favor configuration.
    assert [e['components']['deployable']['base_cost'] for e in p['entities']] == [16, 10, 9, 8, 27, 15, 13, 16, 15, 7, 14, 7]
    cards = sorted(p['entities'], key=lambda e: (e['components']['deployable']['base_cost'], e['id']))
    assert sum(e['components']['deployable']['base_cost'] for e in cards[:8]) <= 99
    sim = Engine.create(Compiler().compile(p), seed=2311)
    for i, card in enumerate(cards[:9]):
        sim.submit({'action': 'deploy', 'definition': card['id'], 'position': {'row': i//4, 'col': i%4}, 'alias': 'card'+str(i)}, at=i)
    sim.advance(9)
    assert len([e for e in sim.session.events if e['type'] == 'command.accepted']) == 8
    rejected = [e for e in sim.session.events if e['type'] == 'command.rejected']
    assert len(rejected) == 1 and rejected[0]['payload']['reason'] == 'capacity'
    assert sim.ctx.resources.current('system/battle', 'dp') == 16
    assert len([e for e in sim.session.world.entities() if 'native_training_card' in e['tags']]) == 8
    roundtrip(sim)


def test_fixed12_overlay_keeps_native_cards_and_forbids_predefined_public_card():
    p = apply_fixed12_overlay(json.loads(INPUT.read_bytes())); _, native = source_cards()
    profile = p['scenarioDraft']['metadata']['roster_selection_profile']
    assert profile['native_cards'] == native and profile['native_training_deck_legal'] is False
    assert profile['selected_definitions'] == p['scenarioDraft']['roster']
    # Only the control test's resource supply changes; native waves/controls/NPC remain.
    p['scenarioDraft']['resources']['dp']['initial'] = 99
    p['scenarioDraft']['metadata']['test_scope'] = 'public deck boundary under full source scene, with explicit test DP supply'
    sim = Engine.create(Compiler().compile(p), seed=2312)
    sim.submit({'action': 'deploy', 'definition': 'unit/ch1_predefined_adnach_e0_l20', 'position': {'row': 3, 'col': 3}}, at=1)
    sim.advance(2)
    rejected = [e for e in sim.session.events if e['type'] == 'command.rejected']
    assert len(rejected) == 1 and 'roster' in rejected[0]['payload']['reason']
    assert sim.ctx.resources.current('system/battle', 'dp') == 99
    assert len([e for e in sim.session.world.entities() if e['definition_id'] == 'unit/ch1_predefined_adnach_e0_l20']) == 1
    roundtrip(sim)
