"""Real external ack/lock/gating with durable restoration and command replay."""
import hashlib
import json
from pathlib import Path
import sys
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.control_driver.public_ack_v2 import PublicAckDriver


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def model():
    lock = {'op':'input_lock','target':'battle','parameters':{'key':'dialogue','enabled':True}}
    unlock = deepcopy(lock)
    unlock['parameters']['enabled'] = False
    controls = [{'id':'control/dialogue','kind':'control','clock_policy':'logical','ack_policy':'external',
                 'on_start':[lock], 'on_complete':[unlock], 'on_cancel':[deepcopy(unlock)],
                 'steps':[{'kind':'ack','key':'line/1'}, {'kind':'ack','key':'line/2'}]}]
    return {'schemaVersion':2, 'manifest':{'id':'package/public_ack_driver','requires':['preset/ark_standard']},
        'controls':controls, 'scenarioDraft':{'id':'scene/public_ack_driver','ruleset':'ruleset/ark_standard',
        'map':{'rows':1,'cols':1}, 'objectives':{}, 'resources':{},
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[
            {'actions':[{'kind':'control','definition':'control/dialogue','instanceAlias':'story/native',
                         'managed':True,'blocks_wave':True,'blocks_fragment':True}]},
            {'actions':[{'kind':'effects','effects':[{'op':'emit','target':'battle','event':'proof.next_fragment'}]}]}
        ]}]}}}


def main():
    core = implementation_digest()
    out = ROOT / 'validation/campaign/public_ack_driver_v2'
    assert not out.exists()
    out.mkdir(parents=True)
    data = model()
    (out/'input.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8',newline='')
    program = Compiler().compile(data)
    sim = Engine.create(program, seed=610)
    driver = PublicAckDriver(sim)
    driver.advance_to(1)
    assert len(driver.submitted) == 1 and driver.submitted[0]['at'] == 2
    assert sim.ctx.state()['input_locks'] and not any(e['type']=='proof.next_fragment' for e in sim.session.events)
    disk = out/'ordered.checkpoint.json'
    bundle = {'simulation':sim.checkpoint(), 'driver':driver.checkpoint()}
    pin = write_ordered(disk,bundle)
    loaded = load_bound(disk,pin)
    restored = Engine.restore(program,loaded['simulation'])
    peer = PublicAckDriver(restored,loaded['driver'])
    driver.advance_to(8)
    peer.advance_to(8)
    head = replay(program, sim.export_replay())
    assert sim.checkpoint() == restored.checkpoint() == head.checkpoint()
    assert sim.snapshot() == restored.snapshot() == head.snapshot()
    assert driver.checkpoint() == peer.checkpoint()
    assert not sim.ctx.state()['input_locks']
    assert len(driver.submitted) == 2
    outcomes = [e for e in sim.session.events if e['type']=='command.accepted']
    assert len(outcomes) == 2 and [e['time'] for e in outcomes] == [2,4]
    next_fragment = [e for e in sim.session.events if e['type']=='proof.next_fragment']
    assert len(next_fragment) == 1 and next_fragment[0]['time'] >= 4
    negatives = []
    for name, mutate in [('cursor_bool',lambda d:d.update(cursor=True)),
                         ('wrong_program',lambda d:d.update(program='0'*64)),
                         ('wrong_clock',lambda d:d.update(at=999)),
                         ('missing_ack',lambda d:d['submitted'][0].update(step=999))]:
        state = deepcopy(loaded['driver'])
        mutate(state)
        try:
            PublicAckDriver(Engine.restore(program,loaded['simulation']),state)
        except ValueError:
            negatives.append({'case':name,'rejected':True})
        else:
            raise AssertionError(name)
    assert core == implementation_digest()
    report = {'passed':True,'core':core,'disk_sha':pin,'event_count':len(sim.session.events),
              'actual_ack_commands':driver.submitted,'accepted_ticks':[e['time'] for e in outcomes],
              'next_fragment_tick':next_fragment[0]['time'],'checkpoint_equal':True,'head_replay_equal':True,
              'negative_cases':negatives,'helper_sha':sha(ROOT/'tools/control_driver/public_ack_v2.py'),
              'scope':'Explicit one-tick external response model and public command replay, not native wall-clock pause or chapter6 whole-stage evidence'}
    target = out/'verification.json'
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'passed':True,'sha':sha(target),'events':report['event_count']}))


if __name__ == '__main__':
    main()
