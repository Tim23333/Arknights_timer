"""Bind the immutable 0-11 battle to independent source, scope and complete-run reviews."""
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
    original=ROOT/'packages/mainline/contracts/main_00-11.json';contract=deepcopy(load(original))
    target=ROOT/'packages/mainline/contracts/main_00-11.reviewed.json'
    content=ROOT/'packages/mainline/v2/main_00-11.json'
    scope_path='validation/campaign/shared_actor_scope_00_11_gate_review.json';scope=load(ROOT/scope_path)
    scope_ref={'path':scope_path,'sha256':sha(ROOT/scope_path)}
    source_ref={'path':'validation/campaign/00_11_source_consumer_review.json',
        'sha256':sha(ROOT/'validation/campaign/00_11_source_consumer_review.json')}
    contract['mechanic_tests']=deepcopy(contract['shared_witness_proposals'])
    for key,refs in contract['mechanic_tests'].items():
        for ref in refs:
            matches=[r for r in scope['approved_cases'] if r['case']==ref['case'] and r['source_evidence_path']==ref['path']
                and r['source_evidence_sha256']==ref['sha256'] and (not ref.get('helper_path') or r['helper_path']==ref['helper_path'])]
            if len(matches)!=1:raise ValueError('Missing/ambiguous actor scope: '+key)
            match=matches[0];ref.update(helper_path=match['helper_path'],helper_sha256=match['helper_sha256'],shared_scope_review=scope_ref)
            if 'test_node_id' in ref:ref['witness_kind']='full_suite_source_node'
    run_path='validation/campaign/m12_primary_00_11_full_20261002.json'
    run=load(ROOT/run_path)
    if run.get('passed') is not True:raise ValueError('0-11 complete validation has not finished')
    stage_ref={'path':run_path,'sha256':sha(ROOT/run_path),'witness_kind':'completed_stage'}
    for key in contract['required_mechanics']:
        if key.startswith('stage:'):contract['mechanic_tests'][key]=[stage_ref]
    contract.update(status='reviewed_declared_model_profile_ready_for_external_receipt',source_review_pending=False,
        semantic_source_review=source_ref,shared_actor_scope_review=scope_ref)
    contract['reviewed_typed_gaps']={'model_gap':[],'client_pending':contract.get('client_pending',[]),
        'historical_draft_gaps_preserved':contract.get('typed_gaps',{})}
    target.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    case={'native_id':'main_00-11','level_id':'level_main_00-11','expected_native_spawns':37,
        'planned_content':content.relative_to(ROOT).as_posix(),'planned_commands':'scenarios/mainline/v2/main_00-11/commands.json',
        'planned_contract':target.relative_to(ROOT).as_posix(),'native_source_sha256':contract['native_source_sha256']}
    expected={'content_sha256':sha(content),'commands_sha256':sha(ROOT/case['planned_commands']),
        'native_source_sha256':case['native_source_sha256'],'implementation_sha256':implementation_digest()}
    roster=load(ROOT/'packages/campaign/roster.reference.json');program=Compiler().compile(content)
    contract_gate(program,case,roster,contract,sha(content))
    source_review_gate(ROOT,[source_ref],expected)
    refs={(r['path'],r['sha256']) for key,values in contract['mechanic_tests'].items() if not key.startswith('stage:') for r in values}
    receipt_inputs={'test_evidence':[{'path':p,'sha256':s} for p,s in sorted(refs)],'shared_scope_reviews':[scope_ref],
        'stage_evidence':[stage_ref],'stage_content_path':case['planned_content'],'stage_commands_path':case['planned_commands'],
        'suite_launch_provenance':{'path':'validation/campaign/m12_primary_launch_provenance_20261002.json',
            'sha256':sha(ROOT/'validation/campaign/m12_primary_launch_provenance_20261002.json')}}
    witness_gate(ROOT,contract,receipt_inputs,expected)
    result={'schema':'ark-sim/reviewed-external-contract-preparation/v2','passed':True,'case':case,
        'contract_sha256':sha(target),'content_sha256':sha(content),'commands_sha256':expected['commands_sha256'],
        'source_review_accepted':True,'shared_scope_accepted':True,'resolved_requirements':len(contract['required_mechanics']),
        'required_requirements':len(contract['required_mechanics']),'whole_stage_ready':True,'receipt_inputs':receipt_inputs,
        'formal_approval':False,'receipt_written':False}
    path=ROOT/'validation/campaign/00_11_external_contract_preparation_20261002.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':True,'requirements':len(contract['required_mechanics']),'whole_stage_ready':True}))


if __name__=='__main__':main()
