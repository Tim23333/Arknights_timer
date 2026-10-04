"""Link required deployed-actor checks to exact executed cases and event receipts."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_mechanism_evidence import resolve_requirements,sha

BASE = 'validation/campaign/deployed_six_m12_final_20261002.json'
OFFENSIVE = 'validation/campaign/deployed_offensive_m12_final_20261002.json'
SUPPORT = 'validation/campaign/deployed_support_m12_extended.json'
CASES = {
    'myrtle':[(BASE,'myrtle_dp_heal_window',['healing.accepted','resource.changed']),
        (SUPPORT,'myrtle_vanguard_regen_and_source_exit',['regeneration.accepted','command.accepted'])],
    'bpipe':[(BASE,'bpipe_triple_rng',['damage.accepted']),
        (BASE,'bpipe_kill_dp',['combat.kill','resource.changed']),
        (OFFENSIVE,'bpipe_splash_excludes_primary',['damage.accepted']),
        (OFFENSIVE,'bpipe_defense_block_and_expiry',['damage.accepted','buff.removed']),
        (OFFENSIVE,'bpipe_deck_sp_and_refund_cap',['command.accepted','resource.changed'])],
    'angel':[(BASE,'angel_auto_burst',['attack.accepted','damage.accepted']),
        (OFFENSIVE,'angel_force_and_empty_auto',['command.rejected','ability.started']),
        (OFFENSIVE,'angel_retargets_after_first_death',['combat.kill','damage.accepted']),
        (OFFENSIVE,'angel_blessing_deploy_and_retire',['command.accepted','buff.applied','buff.removed'])],
    'amgoat':[(BASE,'eyja_random_targets',['projectile.launched','damage.accepted']),
        (OFFENSIVE,'eyja_six_limit_and_filter',['projectile.launched','damage.accepted']),
        (OFFENSIVE,'eyja_empty_half_open',['ability.started','ability.finished','resource.changed']),
        (OFFENSIVE,'eyja_deploy_float_and_caster_aura_retire',['command.accepted','damage.accepted','resource.changed'])],
    'plosis':[(BASE,'plosis_three_heals',['healing.accepted']),
        (SUPPORT,'plosis_time_event_highest_and_source_exit',['command.accepted','resource.changed']),
        (SUPPORT,'plosis_forty_second_mode_and_late_packet_gate',['healing.accepted','resource.changed'])],
    'demkni':[(BASE,'saria_heal_sp',['healing.accepted','resource.changed']),
        (SUPPORT,'saria_five_layers_atk_and_actual_defense',['damage.accepted']),
        (SUPPORT,'saria_arts_only_and_source_exit',['command.accepted','damage.accepted']),
        (SUPPORT,'saria_recipient_emission_freeze_same_frame_finish',['healing.accepted','ability.finished']),
        (SUPPORT,'canonical_regeneration_does_not_return_saria_sp',['regeneration.accepted','resource.changed'])],
}


def audit():
    from ark_sim.adapters.api import implementation_digest
    core = implementation_digest()
    package = ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json'
    requirements,missing = {},[]
    for actor, rows in CASES.items():
        for path, case, events in rows:
            key = actor+'/'+case
            evidence = ROOT/path
            if not evidence.exists():
                missing.append({'mechanism':key,'expected_evidence':path,'reason':'run not yet complete'})
                continue
            value = json.loads(evidence.read_bytes())
            if value.get('passed') is not True:
                missing.append({'mechanism':key,'expected_evidence':path,'reason':'run not passed; see preserved failure'})
                continue
            requirements[key] = [{'path':path,'sha256':sha(evidence),'case':case,'required_event_types':events}]
    resolved = resolve_requirements(ROOT,requirements,core,sha(package))
    return {'schema':'ark-sim/deployed-case-coverage/v1','implementation_sha256':core,
        'input_package':package.relative_to(ROOT).as_posix(),'input_package_sha256':sha(package),
        'required_case_count':sum(len(rows) for rows in CASES.values()),'resolved_case_count':len(resolved),
        'actor_count':len(CASES),'requirements':requirements,'resolved':resolved,'missing':missing,
        'complete_listed_cases':not missing,
        'scope':'Only the 23 listed endpoint/extension checks; other six operators and whole-stage review remain separate',
        'client_pending':['Native clocks/FSM/RNG/comparators and source version alignment'],
        'source_audit_still_required':True,'formal_approval':False,
        'resolver_sha256':sha(ROOT/'tools/campaign_mechanism_evidence.py'),'auditor_sha256':sha(Path(__file__))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/m12_deployed_case_coverage.json')
    args = parser.parse_args()
    d = audit()
    args.output.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:d[k] for k in ['required_case_count','resolved_case_count','complete_listed_cases','formal_approval']}))


if __name__ == '__main__':
    main()
