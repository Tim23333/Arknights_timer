"""Independent bounded W model review; no native/full-boss approval."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.compare import first_difference
    from ark_sim.tools.replay import replay
    path = ROOT/'packages/campaign/chapter01_models/w/probe.json'
    base = json.loads(path.read_bytes())
    # Four co-located actor identities: three captured bombs each independently
    # hit all four area members, including the fourth non-captured actor.
    data = deepcopy(base)
    target = data['scenarioDraft']['initialEntities'][1]
    data['scenarioDraft']['initialEntities'] = [data['scenarioDraft']['initialEntities'][0]]+[
        dict(target, instanceAlias='review_target'+str(i)) for i in range(4)]
    data['abilities'].append({'id': 'ability/review_w_half_hp', 'kind': 'ability',
        'activation': {'mode': 'manual', 'on_start': [{'op': 'modify_resource',
            'target': 'source', 'resource': 'hp', 'value': 5000}]},
        'parameters': {'blocks_attacks': False}, 'timeline': []})
    data['entities'][0]['components']['abilities'].append('ability/review_w_half_hp')
    sim = Engine.create(Compiler().compile(data), seed=812)
    w = sim.session.world.resolve('w')
    sim.submit({'action': 'skill', 'source': 'w', 'ability': 'ability/review_w_half_hp'})
    sim.advance(3)
    assert sim.ctx.resources.current(w, 'mode') == 1
    assert sim.ctx.get(w, ('attributes', 'base', 'atk')) == 470
    starts = [e for e in sim.session.events if e['type']=='ability.started' and e['payload']['ability']=='ability/chapter01_w_c4_1']
    assert len(starts)==1, 'T1 must actually auto-start on entry'
    start_tick = starts[0]['time']
    assert len(starts[0]['payload']['targets']) == 3
    sim.advance(47)
    checkpoint = sim.checkpoint()
    restored = Engine.restore(sim.program, checkpoint)
    sim.advance(70); restored.advance(70)
    hp = [sim.ctx.resources.current('review_target'+str(i),'hp') for i in range(4)]
    assert hp == [2762]*4, hp
    damage = [e for e in sim.session.events if e['type']=='damage.accepted']
    assert len(damage)==12 and all(abs(e['payload']['amount']-746)<1e-8 for e in damage)
    assert {e['time'] for e in damage}=={start_tick+114}
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    difference = first_difference(sim.snapshot(), replay(sim.program, sim.export_replay()).snapshot())
    assert difference is None, difference
    # A live source withdrawn before the authored impact follows the same
    # explicit cancellation policy as source death, not target death.
    retired = Engine.create(Compiler().compile(data), seed=812)
    retired.submit({'action': 'skill', 'source': 'w', 'ability': 'ability/review_w_half_hp'})
    retired.advance(10)
    retired.ctx.lifecycle.retire('w','withdrawn')
    retired.advance(115)
    assert not [e for e in retired.session.events if e['type']=='damage.accepted']
    meta = data['manifest']['metadata']
    assert meta['full_enemy_implemented'] is False
    assert 'normal_attack_not_authored' in meta['model_gaps']
    return {'schema':'ark-sim/chapter01-w-independent-review/v1','passed':True,
        'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'implementation_digest':implementation_digest(),
        'program_fingerprint':sim.program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,
        'automatic_T1_start_tick':start_tick,'targets_captured':3,'damage_events':12,'amount_per_hit':746,
        'impact_tick':start_tick+114,'remaining_hp':hp,'checkpoint_equal':True,'replay_equal':True,
        'source_withdraw_cancels':True,'full_boss_approved':False,'formal_stage_approved':False}


if __name__=='__main__':
    result=run()
    output=ROOT/'validation/campaign/chapter01_w_independent_review.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result))
