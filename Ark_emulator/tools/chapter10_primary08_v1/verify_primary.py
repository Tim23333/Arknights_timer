"""Fresh primary import with positive/negative arbitrary resource channels."""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2];sys.path.insert(0, str(ROOT))
import ark_sim
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import digest, thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter10_primary08_v1.promote import NEW, inventory
from tools.campaign_resource_channel_v1.fixture import package


def main():
    output = ROOT / 'validation/campaign/chapter10_primary08_v1/actual.primary.v1.json'
    if output.exists():raise FileExistsError(output)
    assert implementation_digest() == NEW and Path(ark_sim.__file__).resolve().parent == ROOT / 'ark_sim'
    before = inventory(ROOT / 'ark_sim')
    report = {'schema': 'ark-sim/primary-resource-channel-check/v1', 'core': NEW,
              'passed': False, 'cases': [], 'source_before': before, 'whole_stage': False, 'client_verified': False}
    try:
        for name, delta, initial, capacity, expected in [('charge_q', 1.25, 1, 9, 4.75), ('flux', -2.5, 21, 31, 13.5)]:
            p = package(key=name, delta=delta, initial=initial, cap=capacity, interval=.4, duration=1.2)
            program = Compiler().compile(p)
            a = Engine.create(program, seed=803)
            a.advance(20)
            path = Path(os.environ['ARKSIM_RUN_DIR']) / (name + '.checkpoint.json')
            pin = write_ordered(path, a.checkpoint())
            b = Engine.restore(program, load_bound(path, pin))
            assert a.checkpoint() == b.checkpoint()
            a.advance(50);b.advance(50)
            h = replay(program, a.export_replay())
            assert a.checkpoint() == b.checkpoint() == h.checkpoint()
            assert list(a.session.events) == list(b.session.events) == list(h.session.events)
            channel = thaw(next(iter(a.ctx.attachments.state()['instances'].values())))
            value = a.ctx.resources.current('target', name)
            assert channel['packets'] == 3 and channel['reason'] == 'complete' and not channel['active']
            assert value == expected
            assert a.ctx.resources.current('source', 'hp') == 23177 and a.ctx.resources.current('target', 'hp') == 17173
            report['cases'].append({'resource': name, 'value': value, 'expected': expected,
                                    'actual_packets': channel['packets'], 'checkpoint_sha256': pin,
                                    'complete_CP_head_equal': True, 'checkpoint_digest': digest(a.checkpoint())})
        report['passed'] = True
    except Exception:report['error'] = traceback.format_exc()
    report['source_after'] = inventory(ROOT / 'ark_sim')
    report['actual_modules'] = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
                               if name.startswith('ark_sim') and getattr(module, '__file__', None)}
    report['identity_stable'] = (before == report['source_after'] and implementation_digest() == NEW
                                and all(Path(path).is_relative_to(ROOT / 'ark_sim') for path in report['actual_modules'].values()))
    report['actual_exit'] = 0 if report['passed'] and report['identity_stable'] else 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': report['passed'], 'actual_exit': report['actual_exit'], 'error': report.get('error')}))
    return report['actual_exit']


if __name__ == '__main__':raise SystemExit(main())
