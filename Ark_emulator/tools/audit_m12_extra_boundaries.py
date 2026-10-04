"""Independent event arithmetic for the four supplementary M12 boundaries."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_mechanism_evidence import resolve_case,sha


def eq(actual,expected):
    assert abs(actual-expected) < 1e-7, (actual,expected)


def main():
    from ark_sim.adapters.api import implementation_digest
    core = implementation_digest()
    package = ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json'
    rows = []
    kalts_path = 'validation/campaign/kalts_boundaries_m12_final_20261002.json'
    angel_path = 'validation/campaign/angel_blessing_damage_m12_final_20261002.json'
    for path,case,events in [(kalts_path,'normal_defense_inside_outside_reentry',['damage.accepted']),
        (kalts_path,'s3_defense_inside_outside_reentry',['damage.accepted']),
        (kalts_path,'other_killer_keeps_no_kill_penalty',['combat.kill','damage.accepted']),
        (angel_path,'friend_damage_capacity_source_exit',['damage.accepted','healing.accepted'])]:
        reference = {'path':path,'sha256':sha(ROOT/path),'case':case,'required_event_types':events}
        resolved = resolve_case(ROOT,reference,core,sha(package))
        d = json.loads((ROOT/path).read_bytes())
        actual = d['cases'][case]
        observed = actual['events']
        if case in ['normal_defense_inside_outside_reentry','s3_defense_inside_outside_reentry']:
            packets = [e for e in observed if e['type'] == 'damage.accepted' and
                e['payload'].get('ability') == 'ability/kalts_boundary_physical']
            assert [e['time'] for e in packets] == [1,3,5]
            defense = 389*(3 if case.startswith('s3') else 1)
            damage = max(1000-defense,1000*.05)
            for e,value in zip(packets,[damage,1000,damage]):
                eq(e['payload']['amount'],value)
        elif case == 'other_killer_keeps_no_kill_penalty':
            kills = [e for e in observed if e['type'] == 'combat.kill']
            assert len(kills) == 1 and kills[0]['time'] == 1
            penalty = [e for e in observed if e['type'] == 'damage.accepted' and
                e['payload']['source'] == e['payload']['target']]
            assert len(penalty) == 1 and penalty[0]['time'] == 600
            eq(penalty[0]['payload']['amount'],5177*.5)
            assert kills[0]['payload']['source'] != penalty[0]['payload']['source']
            cleared = [e for e in observed if e['type'] == 'resource.changed' and
                e['payload']['resource'] == 'no_kill' and e['payload']['delta'] < 0]
            assert len(cleared) == 1 and cleared[0]['time'] == 600
        else:
            uid = next(e['id'] for e in actual['entity_identities'] if e['definition'] == 'unit/char_151_myrtle')
            packets = [e for e in observed if e['type'] == 'damage.accepted' and e['payload']['source'] == uid]
            assert [e['time'] for e in packets] == [15,54]
            for e,value in zip(packets,[520*1.06-50,520-50]):
                eq(e['payload']['amount'],value)
            heals = [e for e in observed if e['type'] == 'healing.accepted']
            assert len(heals) == 1 and heals[0]['time'] == 1
            eq(heals[0]['payload']['amount'],1565*1.1-1000-25/30)
            pulse = [e for e in observed if e['type'] == 'regeneration.accepted' and e['time'] == 1]
            assert len(pulse) == 1 and pulse[0]['id'] < heals[0]['id']
            resources = next(e['resources'] for e in actual['actor_runtime'] if e['id'] == uid)
            eq(resources['hp'],1565)
        rows.append({'case':case,'independent_event_math':'passed','identity':resolved})
    result = {'schema':'ark-sim/extra-boundary-artifact-review/v1','passed':True,
        'implementation_sha256':core,'input_package_sha256':sha(package),'cases':rows,
        'scope':'Independent arithmetic on preserved event receipts; no additional combat runs',
        'tests':[{'path':Path(__file__).relative_to(ROOT).as_posix(),'source_sha256':sha(Path(__file__)),'result':'passed'}],
        'formal_approval':False,'client_pending_preserved':True}
    output = ROOT/'validation/campaign/m12_extra_boundary_event_review_20261002.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':True,'cases':len(rows),'output':str(output)}))


if __name__ == '__main__':
    main()
