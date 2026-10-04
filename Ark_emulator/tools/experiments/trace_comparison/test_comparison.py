"""Intermediate mismatches cannot disappear behind a matching final state."""
from copy import deepcopy
import pytest
from tools.compare_campaign_trace import compare


def fixture():
    identity = {k:k+'/test' for k in ('stage_id','game_build','platform','content_identity','roster_identity','commands_identity','episode_identity')}
    def trace(origin,frames):
        return {'schema':'ark-sim/intermediate-trace/v1','origin':origin,'identity':deepcopy(identity),
                'samples':[{'frame':f,'frame_before':f,'frame_after':f,'complete':True,
                            'values':{'enemy/1/hp':hp,'enemy/1/state':'move','enemy/1/col':.1}} for f,hp in frames]}
    native = trace('synthetic_test',[(0,100),(2,80),(4,60)])
    model = trace('ark_sim',[(0,100),(1,80),(2,60)])
    contract = {'schema':'ark-sim/intermediate-comparison-contract/v1','identity':identity,'native_frames':[0,2,4],
                'time_mapping':{'native_origin':0,'model_origin':0,'numerator':1,'denominator':2,'evidence':'synthetic fixture mapping'},
                'fields':[{'name':'hp','native_key':'enemy/1/hp','model_key':'enemy/1/hp','mode':'exact'},
                          {'name':'state','native_key':'enemy/1/state','model_key':'enemy/1/state','mode':'exact'}],
                'uncovered_requirements':['client capture and full field coverage']}
    return native,model,contract


def test_explicit_mapping_matches_and_never_self_approves_accuracy():
    a,b,c=fixture();r=compare(a,b,c)
    assert r['comparison_passed'] and r['compared_values']==6
    assert r['actual_game_accuracy_verified'] is False


def test_middle_hp_mismatch_is_retained_even_when_final_matches():
    a,b,c=fixture();b['samples'][1]['values']['enemy/1/hp']=81;r=compare(a,b,c)
    assert not r['comparison_passed'] and r['first_difference']['native_frame']==2
    assert r['first_difference']['native']==80 and r['first_difference']['model']==81


@pytest.mark.parametrize('mutation',[lambda b:b['samples'].pop(1),lambda b:b['samples'][1]['values'].pop('enemy/1/hp')])
def test_missing_frame_or_field_fails(mutation):
    a,b,c=fixture();mutation(b);assert not compare(a,b,c)['comparison_passed']


@pytest.mark.parametrize('mutation',[lambda a:a['samples'][0].update(frame_after=1),lambda a:a['samples'][0].update(complete=False),lambda a:a['samples'].append(deepcopy(a['samples'][0]))])
def test_mixed_incomplete_duplicate_sample_rejected(mutation):
    a,b,c=fixture();mutation(a)
    with pytest.raises(ValueError):compare(a,b,c)


def test_wrong_version_rejected_before_comparison():
    a,b,c=fixture();a['identity']['game_build']='other'
    with pytest.raises(ValueError,match='identity differs'):compare(a,b,c)


def test_unrepresentable_time_is_a_reported_gap_not_rounded():
    a,b,c=fixture();c['native_frames']=[1];r=compare(a,b,c)
    assert r['first_difference']['reason']=='model_time_not_representable'


def test_bool_is_not_integer_hp():
    a,b,c=fixture();a['samples'][0]['values']['enemy/1/hp']=True;b['samples'][0]['values']['enemy/1/hp']=1
    assert not compare(a,b,c)['comparison_passed']


def test_coordinate_tolerance_records_exact_difference_and_requires_evidence():
    a,b,c=fixture();c['fields']=[{'name':'col','native_key':'enemy/1/col','model_key':'enemy/1/col','mode':'absolute_tolerance',
        'semantic_type':'continuous_coordinate','tolerance':1e-6,'evidence':'synthetic numerical precision fixture'}]
    b['samples'][1]['values']['enemy/1/col']=.1000001;assert compare(a,b,c)['comparison_passed']
    b['samples'][1]['values']['enemy/1/col']=.11;r=compare(a,b,c)
    assert r['first_difference']['difference']==pytest.approx(.01)
    c['fields'][0]['evidence']=''
    with pytest.raises(ValueError,match='Tolerance requires'):compare(a,b,c)


def test_tolerance_cannot_hide_discrete_state():
    a,b,c=fixture();c['fields'][0].update(mode='absolute_tolerance',semantic_type='state',tolerance=100,evidence='bad')
    with pytest.raises(ValueError,match='discrete'):compare(a,b,c)


@pytest.mark.parametrize('mutation',[lambda a:a['samples'][0].update(frame_before=False),lambda a:a['samples'][0].update(frame_after=False)])
def test_boolean_frame_guard_is_not_integer_frame(mutation):
    a,b,c=fixture();mutation(a)
    with pytest.raises(ValueError,match='integer'):compare(a,b,c)


def test_boolean_coverage_frame_rejected_before_matching():
    a,b,c=fixture();c['native_frames']=[False,2,4]
    with pytest.raises(ValueError,match='integer'):compare(a,b,c)


@pytest.mark.parametrize('left,right',[({'inext':True},{'inext':1}),([1],[1.0]),({'states':[True]},{'states':[1]})])
def test_nested_rng_or_state_fields_preserve_types(left,right):
    a,b,c=fixture();a['samples'][0]['values']['enemy/1/hp']=left;b['samples'][0]['values']['enemy/1/hp']=right
    assert not compare(a,b,c)['comparison_passed']
