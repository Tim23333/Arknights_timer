"""Source reviews cannot substitute a different subject or a raw-byte report."""
from copy import deepcopy
import json
import pytest
from tools.campaign_model_acceptance import SEMANTIC_CHECKS,sha,source_review_gate


def fixture(tmp_path):
    source=tmp_path/'native.json';source.write_text('{"native":"fixture"}',encoding='utf8')
    proof=tmp_path/'consumer.json';proof.write_text(json.dumps({'passed':True,'scope':'isolated source-gate fixture'}),encoding='utf8')
    expected={'content_sha256':'content','native_source_sha256':'native','implementation_sha256':'core'}
    review={'schema':'ark-sim/source-consumer-review/v2','passed':True,'status':'approved_for_declared_model_profile',
        'subject_model_content_sha256':'content','subject_native_source_sha256':'native','implementation_sha256':'core',
        'reviewer':'independent-fixture-reviewer','pending_model_gaps':[],
        'source_locks':[{'path':'native.json','sha256':sha(source)}],
        'checks':{k:'passed' for k in SEMANTIC_CHECKS},'consumer_evidence':{k:[{'path':'consumer.json','sha256':sha(proof),'claim':k}] for k in SEMANTIC_CHECKS}}
    path=tmp_path/'review.json'
    return expected,review,path


def run(tmp_path,review,path,expected):
    path.write_text(json.dumps(review),encoding='utf8')
    return source_review_gate(tmp_path,[{'path':'review.json','sha256':sha(path)}],expected)


def test_explicit_subject_core_and_consumer_categories_resolve(tmp_path):
    expected,review,path=fixture(tmp_path)
    assert run(tmp_path,review,path,expected) is True


@pytest.mark.parametrize('field,value',[
    ('schema','ark-sim/first-model-original-field-review/v1'),('subject_model_content_sha256','other'),
    ('subject_native_source_sha256','other'),('implementation_sha256','old'),
    ('status','blocked_current_0fb_complete_conversion'),('pending_model_gaps',['unconsumed']),
    ('reviewer',True),('source_locks',[]),('passed',False)])
def test_wrong_scope_blocked_or_incomplete_review_rejected(tmp_path,field,value):
    expected,review,path=fixture(tmp_path);review[field]=value
    with pytest.raises(ValueError):run(tmp_path,review,path,expected)


@pytest.mark.parametrize('field',['checks','consumer_evidence'])
def test_missing_semantic_category_rejected(tmp_path,field):
    expected,review,path=fixture(tmp_path);review[field].pop('native_enemy_dependencies')
    with pytest.raises(ValueError):run(tmp_path,review,path,expected)


def test_changed_source_and_raw_report_cannot_replace_semantic_review(tmp_path):
    expected,review,path=fixture(tmp_path);(tmp_path/'native.json').write_text('{}',encoding='utf8')
    with pytest.raises(ValueError,match='source lock'):run(tmp_path,review,path,expected)


def test_unexecuted_or_unbound_consumer_claim_rejected(tmp_path):
    expected,review,path=fixture(tmp_path);review['consumer_evidence']['native_enemy_dependencies']=[{'claim':'trust metadata'}]
    with pytest.raises(ValueError,match='frozen executed'):run(tmp_path,review,path,expected)
    expected,review,path=fixture(tmp_path);(tmp_path/'consumer.json').write_text(json.dumps({'passed':False}),encoding='utf8')
    for refs in review['consumer_evidence'].values():refs[0]['sha256']=sha(tmp_path/'consumer.json')
    with pytest.raises(ValueError,match='did not pass'):run(tmp_path,review,path,expected)
