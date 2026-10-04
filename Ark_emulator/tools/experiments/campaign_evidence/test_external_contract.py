"""External acceptance rejects stale inputs and unexecuted mechanism references."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import pytest

from ark_sim import Compiler
from tools import campaign_model_acceptance as acceptance

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def real_inputs():
    draft = acceptance.load(ROOT/'validation/campaign/external_first_model_draft_20261002.json')
    # The prepared draft remains blocked; its completed subset is a reference check.
    contract = acceptance.load(ROOT/draft['case']['planned_contract'])
    reference = acceptance.load(ROOT/'packages/campaign/roster.reference.json')
    program = Compiler().compile(ROOT/draft['case']['planned_content'])
    return draft,contract,reference,program


def test_external_draft_preserves_battle_identity_and_missing_whole_stage_blocks(real_inputs):
    draft,contract,reference,program = real_inputs
    assert draft['battle_byte_exact_copy'] and draft['resolved_mechanism_references']==100
    assert not draft['missing_mechanism_references'] and draft['source_semantic_review_pending']
    missing=deepcopy(contract)
    missing['mechanic_tests'].pop('stage:complete_checkpoint_replay')
    with pytest.raises(ValueError,match='mechanisms'):
        acceptance.contract_gate(program,draft['case'],reference,missing,draft['content_sha256'])


@pytest.mark.parametrize('field,value',[
    ('schema','fake'),('native_level_id','level_main_01-12'),('content_sha256','0'*64),
    ('native_source_sha256','0'*64),
    ('roster_frozen_sha256','0'*64),('pending_model_gaps',['unimplemented']),
    ('required_mechanics',[]),('required_mechanics',[{}]),
    ('native_spawn_by_definition',{'unit/enemy_1000_gopro':34}),
    ('native_spawn_by_definition',{'unit/enemy_1000_gopro':True})])
def test_wrong_contract_binding_is_rejected(real_inputs,field,value):
    draft,original,reference,program = real_inputs
    contract = deepcopy(original);contract['pending_model_gaps']=[];contract[field]=value
    with pytest.raises(ValueError):
        acceptance.contract_gate(program,draft['case'],reference,contract,draft['content_sha256'],require_witnesses=False)


@pytest.mark.parametrize('change',['wrong_skill','unowned','wrong_config','missing_native_id'])
def test_actual_actor_definition_cannot_be_substituted(real_inputs,change):
    draft,original,reference,_ = real_inputs
    data = acceptance.load(ROOT/draft['case']['planned_content'])
    contract = deepcopy(original);contract['pending_model_gaps']=[];row=reference['roster'][0]
    unit=next(e for e in data['entities'] if e.get('metadata',{}).get('native_id')==row['character_id'])
    if change=='wrong_skill':contract['selected_skill_definitions'][row['character_id']]=original['selected_skill_definitions'][reference['roster'][1]['character_id']]
    elif change=='unowned':unit['components']['abilities'].remove(contract['selected_skill_definitions'][row['character_id']])
    elif change=='wrong_config':unit['metadata']['config']['level']=1
    else:unit['metadata'].pop('native_id')
    program=Compiler().compile(data)
    with pytest.raises(ValueError):
        acceptance.contract_gate(program,draft['case'],reference,contract,draft['content_sha256'],require_witnesses=False)


def test_self_declared_contract_cannot_replace_external_receipt(real_inputs,tmp_path):
    draft,contract,reference,_ = real_inputs
    with pytest.raises(ValueError,match='workspace'):
        acceptance.review_gate(tmp_path,draft['case'],reference,'review.json')


def one_node(real_inputs):
    draft,original,_,_ = real_inputs
    key='operator:chen/chen_attack_once_two_hits'
    contract=deepcopy(original);contract['required_mechanics']=[key]
    refs=contract['mechanic_tests'][key]
    receipt={'test_evidence':[{'path':refs[0]['path'],'sha256':refs[0]['sha256']}],
        'suite_launch_provenance':{'path':'validation/campaign/m12_primary_launch_provenance_20261002.json',
            'sha256':acceptance.sha(ROOT/'validation/campaign/m12_primary_launch_provenance_20261002.json')}}
    expected={'content_sha256':draft['content_sha256'],'implementation_sha256':original.get('implementation_sha256',
        'bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11')}
    return contract,receipt,expected,refs[0]


def test_frozen_full_suite_source_node_and_actual_launch_resolve(real_inputs):
    contract,receipt,expected,_=one_node(real_inputs)
    acceptance.witness_gate(ROOT,contract,receipt,expected)


@pytest.mark.parametrize('change',['unreviewed','nonexistent_function','nonexistent_case','malformed_node','wrong_package','wrong_helper'])
def test_forged_or_stale_full_suite_node_rejected(real_inputs,change):
    contract,receipt,expected,ref=one_node(real_inputs)
    if change=='unreviewed':receipt['test_evidence']=[]
    elif change=='nonexistent_function':ref['test_node_id']='tests_v2/test_canonical_roster_trio.py::never_ran[chen_attack_once_two_hits]'
    elif change=='nonexistent_case':ref['test_node_id']='tests_v2/test_canonical_roster_trio.py::test_canonical_mechanism[never_ran]'
    elif change=='malformed_node':ref['test_node_id']='tests_v2/test_canonical_roster_trio.py::test_canonical_mechanism[chen_attack_once_two_hits'
    elif change=='wrong_package':expected['content_sha256']='0'*64
    else:ref['helper_sha256']='0'*64
    with pytest.raises(ValueError):acceptance.witness_gate(ROOT,contract,receipt,expected)


def test_finite_case_keys_include_literal_comprehension_and_appended_case():
    tree=ast.parse("CASES={'base':f, **{'shield_'+k:f for k in ('physical','arts','true')}}\nCASES['late']=f\n")
    assert acceptance.source_case_keys(tree)=={'base','shield_physical','shield_arts','shield_true','late'}
    with pytest.raises(ValueError):acceptance.source_case_keys(ast.parse("CASES={k:f for k in discover()}"))


@pytest.mark.parametrize('change',['wrong_contract_identity','wrong_reviewer','missing_semantic_check','no_evidence'])
def test_metadata_flags_cannot_approve_unreviewed_inputs(real_inputs,tmp_path,change):
    draft,contract,reference,_=real_inputs
    case=deepcopy(draft['case'])
    for key,name in [('planned_content','content.json'),('planned_commands','commands.json'),('planned_contract','contract.json')]:
        (tmp_path/name).write_bytes((ROOT/case[key]).read_bytes());case[key]=name
    expected=acceptance.case_identity(tmp_path,case,reference)
    receipt={'schema':'ark-sim/external-model-review/v2','status':'approved_for_model_run','native_id':case['native_id'],
        'input_identity':expected,'reviewer':'fixture-independent-reviewer',
        'checks':{key:'passed' for key in ['unit_attributes_and_growth','selected_skills_and_talents','native_enemy_dependencies',
            'map_routes_controls_and_objectives','no_substituted_or_ignored_mechanics']},'source_reviews':[],'test_evidence':[]}
    if change=='wrong_contract_identity':receipt['input_identity']['contract_sha256']='0'*64
    elif change=='wrong_reviewer':receipt['reviewer']=True
    elif change=='missing_semantic_check':receipt['checks'].pop('native_enemy_dependencies')
    (tmp_path/'review.json').write_text(json.dumps(receipt),encoding='utf8')
    with pytest.raises(ValueError):acceptance.review_gate(tmp_path,case,reference,'review.json')


def test_known_unconsumed_wave_gating_blocks_complete_flat_model_receipt(real_inputs):
    draft,contract,reference,program=real_inputs
    assert contract['pending_model_gaps']==['native_wave_managed_gating_not_consumed_by_flat_schedule']
    with pytest.raises(ValueError,match='Unresolved model'):
        acceptance.contract_gate(program,draft['case'],reference,contract,draft['content_sha256'])


def test_failed_or_edited_completed_run_cannot_be_consumed_as_success(tmp_path):
    path=tmp_path/'run.json';path.write_text(json.dumps({'passed':False,'checkpoint_resume_equal':True,'replay_equal':True}),encoding='utf8')
    with pytest.raises(ValueError,match='did not pass'):
        acceptance.checked_artifact(tmp_path,{'path':'run.json','sha256':acceptance.sha(path)})
    digest=acceptance.sha(path);path.write_text(json.dumps({'passed':True}),encoding='utf8')
    with pytest.raises(ValueError,match='identity'):
        acceptance.checked_artifact(tmp_path,{'path':'run.json','sha256':digest})


def completed_inputs(real_inputs):
    draft,contract,_,program=real_inputs
    run=acceptance.load(ROOT/'validation/campaign/m12_primary_00_10_full_20261002.json')
    commands=acceptance.load(ROOT/draft['case']['planned_commands'])
    return program,contract,{'content_sha256':draft['content_sha256'],'commands_sha256':draft['commands_sha256']},run,commands


def test_actual_complete_00_10_run_matches_immutable_external_battle_input(real_inputs):
    assert acceptance.completed_stage_gate(*completed_inputs(real_inputs)) is True


@pytest.mark.parametrize('change',['failed','prefix','no_cp','no_replay','old_content','old_commands','old_program','old_runtime',
    'wrong_spawn','wrong_kills','illegal_command','missing_command','missing_observations','leak'])
def test_whole_stage_gate_cannot_promote_narrow_or_stale_run(real_inputs,change):
    program,contract,expected,run,commands=completed_inputs(real_inputs)
    run=deepcopy(run)
    if change=='failed':run['passed']=False
    elif change=='prefix':run['state']['finished']=False
    elif change=='no_cp':run['checkpoint_resume_equal']=False
    elif change=='no_replay':run['replay_equal']=False
    elif change=='old_content':run['package_sha256']='0'*64
    elif change=='old_commands':run['commands_sha256']='0'*64
    elif change=='old_program':run['program_fingerprint']='old'
    elif change=='old_runtime':run['runtime_fingerprint']='old'
    elif change=='wrong_spawn':run['spawned_by_definition']={}
    elif change=='wrong_kills':run['state']['kills']-=1
    elif change=='illegal_command':run['observed_commands'][0]['type']='command.rejected'
    elif change=='missing_command':run['observed_commands'].pop()
    elif change=='missing_observations':run['observations']={}
    else:run['state']['leaks']=1
    with pytest.raises(ValueError):acceptance.completed_stage_gate(program,contract,expected,run,commands)
