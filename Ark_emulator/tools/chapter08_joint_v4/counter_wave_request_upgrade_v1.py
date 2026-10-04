"""Actual false-then-true source requests must preserve required tracking intent."""
import json
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAND = ROOT.parent / 'unpack_work/campaign_wave_track_v2_candidate'
OUT = ROOT / 'validation/campaign/chapter08_wave_request_upgrade_counter_v1/report.json'


def main():
    sys.path.insert(0, str(CAND))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter08_wave_track.test_track_v4 import package, request
    p = package(False)
    s = Engine.create(Compiler().compile(p), seed=8188)
    s.advance(6)
    source = s.session.world.resolve('boss')
    first = s.ctx.timeline.finish_current(source, request(False))
    second = s.ctx.timeline.finish_current(source, request(True))
    assert first is True and second is False
    state = s.ctx.state()['timeline']
    assert state['finish_requests']['0']['parameters']['track_source_at_next_wave'] is False
    assert not state.get('tracking_requests')
    data = {'core': implementation_digest(), 'actual_counter': True, 'input': p,
            'request_order': [request(False), request(True)], 'first_accepted': first,
            'tracking_request_accepted': second, 'actual_timeline': state, 'checkpoint': s.checkpoint(),
            'scope': 'Primitive sameactualmanagedsource false→true request; requiredTrue intent absent. SourcebothBuff ordering needs sourcecomposition decision, no wholeclaim',
            'required_source_intent_missing': True}
    OUT.parent.mkdir(exist_ok=False)
    OUT.write_text(json.dumps(data, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': hashlib.sha256(OUT.read_bytes()).hexdigest(), 'core': data['core'],
                      'required_tracking_recorded': False}))


if __name__ == '__main__':
    main()
