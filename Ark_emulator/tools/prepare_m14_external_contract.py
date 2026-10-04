"""Bind reviewed actor reuse and native Timeline consumers to immutable M14 bytes."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_model_acceptance import contract_gate,load,sha,source_review_gate,witness_gate


def main():
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    source=ROOT/'packages/campaign/mainline_models/level_main_00-10.m14_timeline.json'
    assert sha(source)=='83bfa1829958f80a4f1da95740466326db3f5a8c7143737d728887b3670116d2'
    base=load(ROOT/'packages/mainline/contracts/main_00-10.json')
    scope_path='validation/campaign/shared_actor_scope_m14_gate_review.json';scope=load(ROOT/scope_path)
    source_review_path='validation/campaign/m14_source_consumer_review.json'
    content=ROOT/'packages/mainline/v2/main_00-10.m14.json'
    contract_path=ROOT/'packages/mainline/contracts/main_00-10.m14.json'
    content.write_bytes(source.read_bytes())
    contract=deepcopy(base);contract.update(content_sha256=sha(content),status='reviewed_model_scope_waiting_complete_stage',
        pending_model_gaps=[],source_review_pending=False)
    contract.pop('new_semantic_review_finding',None)
    contract['semantic_source_review']={'path':source_review_path,'sha256':sha(ROOT/source_review_path)}
    scope_ref={'path':scope_path,'sha256':sha(ROOT/scope_path)}
    contract['shared_actor_scope_review']=scope_ref
    for mechanism,refs in contract['mechanic_tests'].items():
        if mechanism.startswith('stage:'):
            continue
        for reference in refs:
            matches=[r for r in scope['approved_cases'] if r['case']==reference['case']
                and r['source_evidence_path']==reference['path'] and r['source_evidence_sha256']==reference['sha256']
                and (not reference.get('helper_path') or r['helper_path']==reference['helper_path'])]
            if len(matches)!=1:raise ValueError('Ambiguous/missing shared scope: '+mechanism)
            match=matches[0];reference.update(shared_scope_review=scope_ref,
                helper_path=match['helper_path'],helper_sha256=match['helper_sha256'])
    run_path='validation/campaign/m14_00_10_full_existing_commands_20261002.json'
    run=load(ROOT/run_path) if (ROOT/run_path).exists() else {}
    stage_evidence=[]
    if run.get('passed') is True:
        stage_ref={'path':run_path,'sha256':sha(ROOT/run_path),'witness_kind':'completed_stage'}
        stage_evidence=[stage_ref]
        for key in [k for k in contract['required_mechanics'] if k.startswith('stage:')]:contract['mechanic_tests'][key]=[stage_ref]
    else:
        for key in [k for k in contract['required_mechanics'] if k.startswith('stage:')]:contract['mechanic_tests'][key]=[]
    contract_path.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    case={'native_id':'main_00-10','level_id':'level_main_00-10','expected_native_spawns':35,
        'planned_content':content.relative_to(ROOT).as_posix(),'planned_commands':'scenarios/mainline/v2/main_00-10/commands.json',
        'planned_contract':contract_path.relative_to(ROOT).as_posix(),'native_source_sha256':contract['native_source_sha256']}
    expected={'content_sha256':sha(content),'commands_sha256':sha(ROOT/case['planned_commands']),
        'native_source_sha256':case['native_source_sha256'],'implementation_sha256':implementation_digest()}
    program=Compiler().compile(content);roster=load(ROOT/'packages/campaign/roster.reference.json')
    contract_gate(program,case,roster,contract,sha(content),require_witnesses=False)
    source_review_gate(ROOT,[contract['semantic_source_review']],expected)
    test_evidence={(r['path'],r['sha256']) for key,refs in contract['mechanic_tests'].items() if not key.startswith('stage:') for r in refs}
    receipt_input={'test_evidence':[{'path':p,'sha256':s} for p,s in sorted(test_evidence)],
        'shared_scope_reviews':[scope_ref],'stage_evidence':stage_evidence,'stage_content_path':case['planned_content'],
        'stage_commands_path':case['planned_commands'],'suite_launch_provenance':{
            'path':'validation/campaign/m12_primary_launch_provenance_20261002.json',
            'sha256':sha(ROOT/'validation/campaign/m12_primary_launch_provenance_20261002.json')}}
    available=deepcopy(contract);available['required_mechanics']=[k for k in contract['required_mechanics'] if contract['mechanic_tests'].get(k)]
    witness_gate(ROOT,available,receipt_input,expected)
    result={'schema':'ark-sim/reviewed-external-contract-preparation/v2','passed':True,'case':case,
        'contract_sha256':sha(contract_path),'content_sha256':sha(content),'commands_sha256':expected['commands_sha256'],
        'source_review_accepted':True,'shared_scope_accepted':True,'resolved_requirements':len(available['required_mechanics']),
        'required_requirements':len(contract['required_mechanics']),'whole_stage_ready':bool(stage_evidence),
        'receipt_inputs':receipt_input,'formal_approval':False,'receipt_written':False}
    output=ROOT/'validation/campaign/m14_external_contract_preparation_20261002.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:result[k] for k in ['passed','resolved_requirements','required_requirements','whole_stage_ready','formal_approval']}))


if __name__=='__main__':main()
