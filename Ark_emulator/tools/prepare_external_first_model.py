"""Keep battle bytes unchanged; place the auditable conversion contract outside runtime."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_model_acceptance import contract_gate,load,sha,witness_gate


def main():
    from ark_sim import Compiler,Engine
    source = ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json'
    draft = ROOT/'packages/mainline/main_00-10.json'
    original = load(source);declared = load(draft)['scenarioDraft']['metadata']['campaign']
    content = ROOT/'packages/mainline/v2/main_00-10.json'
    commands = ROOT/'scenarios/mainline/v2/main_00-10/commands.json'
    contract_path = ROOT/'packages/mainline/contracts/main_00-10.json'
    native = ROOT/'packages/campaign/native_reference/level_main_00-10.json'
    roster = load(ROOT/'packages/campaign/roster.reference.json')
    cases = deepcopy(declared['mechanic_tests'])
    stage_path = ROOT/'validation/campaign/m12_primary_00_10_full_20261002.json'
    stage_evidence = []
    if stage_path.exists() and load(stage_path).get('passed') is True:
        ref = {'path':stage_path.relative_to(ROOT).as_posix(),'sha256':sha(stage_path),'witness_kind':'completed_stage'}
        stage_evidence = [ref]
        for key in ('stage:map_routes_wave_control_enemy_conservation','stage:complete_checkpoint_replay'):
            cases[key] = [ref]
    for refs in cases.values():
        for ref in refs:
            if 'test_node_id' in ref:
                ref['witness_kind'] = 'full_suite_source_node'
    expected = dict(Counter(w['definition'] for w in original['scenarioDraft']['waves']))
    contract = {'schema':'ark-sim/external-model-contract/v2','status':'draft_requires_independent_semantic_review',
        'native_level_id':'level_main_00-10','content_sha256':sha(source),
        'native_source_sha256':sha(native),'roster_frozen_sha256':roster['frozen_sha256'],
        'selected_skill_definitions':declared['selected_skill_definitions'],
        'required_mechanics':declared['required_mechanics'],'mechanic_tests':cases,
        'native_spawn_by_definition':expected,'pending_model_gaps':['native_wave_managed_gating_not_consumed_by_flat_schedule'],
        'new_semantic_review_finding':{'field':'managedByScheduler/dontBlockWave/maxTimeWaitingForNextWave',
            'current_behavior':'fixed absolute flat timing ignores managed-clear dependency',
            'required_fix':'new content preserves native actions and dynamic Timeline membership/gates',
            'classification':'model_gap; complete flat-model victory and CP/replay do not close native flow'},
        'source_review_pending':True,'client_pending':declared['typed_gaps']['client_pending'],
        'source_audit':{'path':'packages/campaign/conversion_drafts/main_00-10.audit.json',
            'sha256':sha(ROOT/'packages/campaign/conversion_drafts/main_00-10.audit.json')},
        'raw_source_review':{'path':'validation/campaign/first_model_original_fields_root_review_20261002.json',
            'sha256':sha(ROOT/'validation/campaign/first_model_original_fields_root_review_20261002.json')},
        'historical_package_metadata_preserved':True,'formal_approval':False}
    for path in (content,commands,contract_path):
        path.parent.mkdir(parents=True,exist_ok=True)
    content.write_bytes(source.read_bytes())
    commands.write_bytes((ROOT/'scenarios/mainline/main_00-10/commands.json').read_bytes())
    contract_path.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    program = Compiler().compile(content);original_program = Compiler().compile(source)
    sim = Engine.create(program,seed=123);original_sim = Engine.create(original_program,seed=123)
    assert program.fingerprint == original_program.fingerprint and sim.runtime_fingerprint == original_sim.runtime_fingerprint
    case = {'native_id':'main_00-10','level_id':'level_main_00-10','expected_native_spawns':35,
        'planned_content':content.relative_to(ROOT).as_posix(),'planned_commands':commands.relative_to(ROOT).as_posix(),
        'planned_contract':contract_path.relative_to(ROOT).as_posix(),'native_source_sha256':sha(native)}
    contract_gate(program,case,roster,contract,sha(content),require_witnesses=False,draft_only=True)
    evidence = {(r['path'],r['sha256']) for refs in cases.values() for r in refs}
    # This checks references, not semantic approval. No review receipt is written.
    available = deepcopy(contract)
    missing = [k for k in contract['required_mechanics'] if not cases.get(k)]
    available['required_mechanics'] = [k for k in contract['required_mechanics'] if cases.get(k)]
    witness_gate(ROOT,available,{'test_evidence':[{'path':p,'sha256':v} for p,v in sorted(evidence) if p != stage_path.relative_to(ROOT).as_posix()],
        'stage_evidence':stage_evidence,'stage_content_path':case['planned_content'],'stage_commands_path':case['planned_commands'],
        'suite_launch_provenance':{'path':'validation/campaign/m12_primary_launch_provenance_20261002.json',
            'sha256':sha(ROOT/'validation/campaign/m12_primary_launch_provenance_20261002.json')}},
        {'implementation_sha256':declared['implementation_sha256'],'content_sha256':sha(content),'commands_sha256':sha(commands)})
    output = ROOT/'validation/campaign/external_first_model_draft_20261002.json'
    result = {'schema':'ark-sim/external-model-draft-validation/v2','passed':True,'case':case,
        'content_sha256':sha(content),'commands_sha256':sha(commands),'contract_sha256':sha(contract_path),
        'program_fingerprint':program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,
        'battle_byte_exact_copy':True,'required_mechanics':len(contract['required_mechanics']),
        'resolved_mechanism_references':len(available['required_mechanics']),'missing_mechanism_references':missing,
        'source_semantic_review_pending':True,'execution_eligible':False,
        'pending_model_gaps':contract['pending_model_gaps'],
        'formal_approval':False,'review_receipt_written':False}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':True,'required_mechanics':len(contract['required_mechanics']),
        'resolved':len(available['required_mechanics']),'missing':missing,'battle_identity_unchanged':True,'output':str(output)}))


if __name__ == '__main__':
    main()
