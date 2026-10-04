"""Independently check support witness event receipts, without rerunning combat."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = 'bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'
PACKAGE = '0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual, expected):
    assert abs(actual-expected) < 1e-7, (actual, expected)


def verify(actual, name):
    events = actual['events']
    identities = {e['definition']: e['id'] for e in actual['entity_identities']}
    def actor(native):
        return identities['unit/'+native]
    def selected(kind, source=None):
        return [e for e in events if e['type'] == kind and (source is None or e['payload'].get('source') == source)]
    assert actual['checkpoint_equal'] and actual['replay_equal']
    assert not selected('command.rejected'), 'Support witnesses require legal commands'
    if name == 'myrtle_vanguard_regen_and_source_exit':
        pulses = selected('regeneration.accepted')
        assert len(pulses) == 60
        assert [e['time'] for e in pulses] == [t for t in range(1,31) for _ in range(2)]
        assert {e['payload']['target'] for e in pulses} == {actor('char_151_myrtle'), actor('char_222_bpipe')}
        for e in pulses:
            close(e['payload']['amount'], 25/30)
    elif name == 'plosis_time_event_highest_and_source_exit':
        values = {r['definition']:r['resources'] for r in actual['actor_runtime']}
        close(values['unit/char_151_myrtle']['sp'], 6+1.3+1)
        close(values['unit/char_358_lisa']['sp'], 1.4*2)
        close(values['unit/char_107_liskam']['sp'], 0)
        gains = [e for e in selected('resource.changed') if e['payload']['resource'] == 'sp' and e['payload']['delta'] > 0]
        assert not any(e['payload']['target'] == actor('char_107_liskam') for e in gains)
    elif name == 'plosis_forty_second_mode_and_late_packet_gate':
        heals = selected('healing.accepted', actor('char_128_plosis'))
        assert [e['time'] for e in heals] == [7+23*i for i in range(52)]+[1234]
        for e in heals:
            close(e['payload']['amount'], 382)
        values = next(r['resources'] for r in actual['actor_runtime'] if r['definition'] == 'unit/char_128_plosis')
        assert values['mode'] == 0
        close(values['sp'], 1.3)
    elif name == 'saria_five_layers_atk_and_actual_defense':
        uid = actor('char_202_demkni')
        attacks = {e['time']:e['payload']['amount'] for e in selected('damage.accepted',uid)}
        close(attacks[17], 513-50)
        close(attacks[629], 513*(1+.05)-50)
        close(attacks[3005], 513*(1+5*.05)-50)
        incoming = [e for e in selected('damage.accepted') if e['payload']['target'] == uid]
        assert len(incoming) == 1 and incoming[0]['time'] == 3000
        close(incoming[0]['payload']['amount'], 2000-631*(1+5*.04))
        values = next(r['resources'] for r in actual['actor_runtime'] if r['id'] == uid)
        close(values['hp'], 2952-(2000-631*1.2))
    elif name == 'saria_arts_only_and_source_exit':
        packets = [e for e in selected('damage.accepted') if e['payload'].get('ability','').startswith('ability/support_probe_')]
        assert [e['time'] for e in packets] == [1,3,5,9]
        for e, value in zip(packets, [100*1.55,100-50,100,100]):
            close(e['payload']['amount'],value)
    elif name == 'saria_recipient_emission_freeze_same_frame_finish':
        heals = selected('healing.accepted',actor('char_202_demkni'))
        assert len(heals) == 1 and heals[0]['time'] == 16
        close(heals[0]['payload']['amount'],513*.35)
        uid = heals[0]['payload']['target']
        finished = selected('ability.finished',uid)
        assert len(finished) == 1 and finished[0]['time'] == 16 and heals[0]['id'] < finished[0]['id']
        assert not any(e['payload']['target'] == uid and e['payload']['resource'] == 'sp' and e['payload']['delta'] > 0
            for e in selected('resource.changed'))
    elif name == 'canonical_regeneration_does_not_return_saria_sp':
        assert selected('regeneration.accepted') and not selected('healing.accepted')
        gains = [e for e in selected('resource.changed') if e['payload']['target'] == actor('char_151_myrtle')
            and e['payload']['resource'] == 'sp' and e['payload']['delta'] > 0]
        assert [(e['time'],e['payload']['delta']) for e in gains] == [(0,6),(29,1)]
    else:
        raise AssertionError('Unexpected support case: '+name)
    return {'case':name, 'event_receipt_math':'passed', 'checkpoint_and_replay_producer_assertions_present':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    d = json.loads(args.evidence.read_bytes())
    assert d['passed'] and d['identity_stable'] and d['pytest_exit_code'] == 0
    assert d['implementation_sha256'] == CORE and d['input_package_sha256'] == PACKAGE
    assert d['source_at_start'] == d['source_at_completion']
    for path, value in d['source_at_start'].items():
        assert sha(Path(path)) == value, 'Reviewed source changed: '+path
    assert len(d['cases']) == len(d['selected_cases']) == 7
    assert {r['case'] for r in d['cases']} == set(d['selected_cases'])
    rows = []
    for r in d['cases']:
        assert r['result'] == 'passed'
        rows.append(verify(r['actual'],r['case']))
    result = {'schema':'ark-sim/deployed-support-artifact-review/v1','passed':True,
        'implementation_sha256':CORE,'input_package_sha256':PACKAGE,'evidence':str(args.evidence),
        'evidence_sha256':sha(args.evidence),'cases':rows,
        'scope':'Independent numerical/event review of producer records; no second combat execution',
        'tests':[{'path':Path(__file__).relative_to(ROOT).as_posix(),'source_sha256':sha(Path(__file__)),'result':'passed'}],
        'formal_approval':False,'client_pending_preserved':True}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':True,'cases':len(rows),'output':str(args.output)}))


if __name__ == '__main__':
    main()
