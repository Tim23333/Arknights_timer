"""Cross-content reuse requires a reviewed exact helper/case and complete scope."""
from copy import deepcopy
import json
import pytest
from tools.campaign_model_acceptance import sha,shared_witness_gate


def setup(tmp_path,static=False):
    helper=tmp_path/'helper.py';helper.write_text('def case(): pass\n',encoding='utf8')
    support=tmp_path/'support.json';support.write_text(json.dumps({'passed':True,'scope':'isolated gate fixture'}),encoding='utf8')
    proof={'schema':'ark-sim/shared-mechanism-case-proof/v2','passed':True,'source_content_sha256':'source',
        'target_content_sha256':'target','implementation_sha256':'core','case':'one','helper_sha256':sha(helper),
        'all_fixtures_accounted_for':True,'reachable_definitions_equal':True,'rule_and_provider_identity_equal':True,
        'effective_inputs_equal':True,'explicit_seed_equal':True,'metadata_nonconsumption_reviewed':True,
        'supporting_evidence':[{'path':'support.json','sha256':sha(support)}]}
    if static:
        proof.update(proof_type='static_source_definition_equivalence',no_runtime_fixture=True,
            static_source_assertions_equal=True,target_case_executed=False)
        proof.pop('all_fixtures_accounted_for')
    review={'schema':'ark-sim/shared-mechanism-review/v2','passed':True,'status':'approved_scoped_definition_use',
        'source_content_sha256':'source','target_content_sha256':'target','implementation_sha256':'core','reviewer':'independent-fixture',
        'source_locks':[{'path':'helper.py','sha256':sha(helper)}],
        'approved_cases':[{'case':'one','source_evidence_path':'source.json','source_evidence_sha256':'source-proof',
            'helper_path':'helper.py','helper_sha256':sha(helper),'proof':{'path':'proof.json','sha256':''}}]}
    reference={'path':'source.json','sha256':'source-proof','case':'one','helper_path':'helper.py','helper_sha256':sha(helper),
        'shared_scope_review':{'path':'review.json','sha256':''}}
    return proof,review,reference,{'content_sha256':'target','implementation_sha256':'core'}


def run(tmp_path,proof,review,reference,expected):
    p=tmp_path/'proof.json';p.write_text(json.dumps(proof),encoding='utf8')
    review['approved_cases'][0]['proof']['sha256']=sha(p)
    r=tmp_path/'review.json';r.write_text(json.dumps(review),encoding='utf8')
    reference['shared_scope_review']['sha256']=sha(r)
    receipt={'shared_scope_reviews':[deepcopy(reference['shared_scope_review'])]}
    return shared_witness_gate(tmp_path,reference,receipt,expected)


@pytest.mark.parametrize('static',[False,True])
def test_explicit_runtime_or_static_scope_keeps_distinct_source_identity(tmp_path,static):
    assert run(tmp_path,*setup(tmp_path,static))=='source'


@pytest.mark.parametrize('field,value',[
    ('target_content_sha256','other'),('source_content_sha256','target'),('implementation_sha256','old'),
    ('status','unapproved_structural_proposal'),('schema','proposal'),('reviewer',True),('source_locks',[])])
def test_unapproved_or_wrong_subject_reuse_rejected(tmp_path,field,value):
    proof,review,ref,expected=setup(tmp_path);review[field]=value
    with pytest.raises(ValueError):run(tmp_path,proof,review,ref,expected)


@pytest.mark.parametrize('field',[
    'all_fixtures_accounted_for','reachable_definitions_equal','rule_and_provider_identity_equal',
    'effective_inputs_equal','explicit_seed_equal','metadata_nonconsumption_reviewed'])
def test_first_fixture_or_missing_nonconsumption_proof_is_insufficient(tmp_path,field):
    proof,review,ref,expected=setup(tmp_path);proof[field]=False
    with pytest.raises(ValueError,match='incomplete'):run(tmp_path,proof,review,ref,expected)


def test_same_case_name_from_different_helper_cannot_borrow_scope(tmp_path):
    proof,review,ref,expected=setup(tmp_path);ref['helper_path']='other.py'
    with pytest.raises(ValueError,match='not independently approved'):run(tmp_path,proof,review,ref,expected)


def test_static_proof_must_not_claim_target_execution(tmp_path):
    proof,review,ref,expected=setup(tmp_path,True);proof['target_case_executed']=True
    with pytest.raises(ValueError,match='must not claim'):run(tmp_path,proof,review,ref,expected)


def test_stale_helper_and_empty_supporting_evidence_rejected(tmp_path):
    proof,review,ref,expected=setup(tmp_path);(tmp_path/'helper.py').write_text('changed',encoding='utf8')
    with pytest.raises(ValueError,match='stale'):run(tmp_path,proof,review,ref,expected)
    proof,review,ref,expected=setup(tmp_path);proof['supporting_evidence']=[]
    with pytest.raises(ValueError,match='supporting'):run(tmp_path,proof,review,ref,expected)
