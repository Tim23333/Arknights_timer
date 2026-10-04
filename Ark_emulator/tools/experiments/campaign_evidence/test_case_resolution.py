"""Negative evidence gates use complete receipts, never combat mocks."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from tools.campaign_mechanism_evidence import resolve_case,resolve_requirements,sha


def receipt(tmp_path,list_style=False):
    source = tmp_path/'probe.py';source.write_text('assert observed == expected\n',encoding='utf8')
    actual = {'checkpoint_equal':True,'replay_equal':True,'program_fingerprint':'program',
        'runtime_fingerprint':'runtime','events':[{'type':'healing.accepted'}]}
    data = {'passed':True,'identity_stable':True,'implementation_sha256':'core',
        'input_package_sha256':'package','selected_cases':['heal'],
        'tests':[{'path':'probe.py','source_sha256':sha(source),'result':'passed'}],
        'cases':[{'case':'heal','result':'passed','actual':actual}] if list_style else {'heal':actual}}
    path = tmp_path/'evidence.json';path.write_text(json.dumps(data),encoding='utf8')
    ref = {'path':'evidence.json','sha256':sha(path),'case':'heal','required_event_types':['healing.accepted']}
    return data,path,ref


@pytest.mark.parametrize('list_style',[False,True])
def test_both_executed_case_shapes_resolve_with_explicit_event_gate(tmp_path,list_style):
    _,_,ref = receipt(tmp_path,list_style)
    result = resolve_requirements(tmp_path,{'heal':[ref]},'core','package')
    assert result['heal'][0]['case']=='heal' and result['heal'][0]['formal_approval'] is False


@pytest.mark.parametrize('field,value',[
    ('passed',False),('identity_stable',False),('implementation_sha256','old'),
    ('input_package_sha256','old'),('selected_cases',[]),('tests',[])])
def test_failed_old_or_unexecuted_receipt_rejected(tmp_path,field,value):
    data,path,ref = receipt(tmp_path);data[field] = value
    path.write_text(json.dumps(data),encoding='utf8');ref['sha256'] = sha(path)
    with pytest.raises(ValueError):resolve_case(tmp_path,ref,'core','package')


@pytest.mark.parametrize('field,value',[
    ('checkpoint_equal',False),('replay_equal',False),('events',[]),('program_fingerprint',''),
    ('runtime_fingerprint','')])
def test_missing_actual_execution_or_replay_is_rejected(tmp_path,field,value):
    data,path,ref = receipt(tmp_path);data['cases']['heal'][field] = value
    path.write_text(json.dumps(data),encoding='utf8');ref['sha256'] = sha(path)
    with pytest.raises(ValueError):resolve_case(tmp_path,ref,'core','package')


def test_edited_helper_and_missing_required_event_rejected(tmp_path):
    _,_,ref = receipt(tmp_path);ref['required_event_types'] = ['damage.accepted']
    with pytest.raises(ValueError,match='event types'):resolve_case(tmp_path,ref,'core','package')
    ref['required_event_types'] = ['healing.accepted']
    (tmp_path/'probe.py').write_text('new expectation\n',encoding='utf8')
    with pytest.raises(ValueError,match='stale'):resolve_case(tmp_path,ref,'core','package')


def test_forged_selected_but_missing_case_rejected(tmp_path):
    data,path,ref = receipt(tmp_path);data['cases'] = {}
    path.write_text(json.dumps(data),encoding='utf8');ref['sha256'] = sha(path)
    with pytest.raises(ValueError,match='missing'):resolve_case(tmp_path,ref,'core','package')


def test_duplicate_list_results_and_wrong_file_identity_rejected(tmp_path):
    data,path,ref = receipt(tmp_path,True);data['cases'].append(deepcopy(data['cases'][0]))
    path.write_text(json.dumps(data),encoding='utf8')
    with pytest.raises(ValueError,match='identity'):resolve_case(tmp_path,ref,'core','package')
    ref['sha256'] = sha(path)
    with pytest.raises(ValueError,match='ambiguous'):resolve_case(tmp_path,ref,'core','package')


def test_workspace_escape_and_empty_requirements_rejected(tmp_path):
    with pytest.raises(ValueError,match='workspace'):
        resolve_case(tmp_path,{'path':'../outside.json'},'core','package')
    with pytest.raises(ValueError,match='empty'):
        resolve_requirements(tmp_path,{},'core','package')
