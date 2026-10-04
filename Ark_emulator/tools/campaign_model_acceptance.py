"""External model contracts and review receipts; battle content stays immutable."""
from collections import Counter
import ast
import json
from pathlib import Path

from tools.campaign_mechanism_evidence import resolve_case,sha,workspace_file
from tools.campaign_progress import fixed_roster,object_identity


def load(path):
    return json.loads(Path(path).read_bytes())


def source_case_keys(tree):
    """Read finite literal CASES keys without importing or executing helper code."""
    def scalar(node,bindings):
        if isinstance(node,ast.Constant):return node.value
        if isinstance(node,ast.Name) and node.id in bindings:return bindings[node.id]
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):
            return scalar(node.left,bindings)+scalar(node.right,bindings)
        raise ValueError('Unsupported dynamic case key expression')
    def keys(node):
        if isinstance(node,ast.Dict):
            result = set()
            for key,value in zip(node.keys,node.values):
                result.update(keys(value) if key is None else [scalar(key,{})])
            return result
        if isinstance(node,ast.DictComp) and len(node.generators) == 1:
            g = node.generators[0]
            if not isinstance(g.target,ast.Name) or g.ifs or g.is_async:
                raise ValueError('Unsupported dynamic case generator')
            values = ast.literal_eval(g.iter)
            if not isinstance(values,(list,tuple)):
                raise ValueError('Case generator must have a finite literal collection')
            return {scalar(node.key,{g.target.id:value}) for value in values}
        raise ValueError('Unsupported dynamic case dictionary')
    result = set()
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id == 'CASES':result.update(keys(node.value))
                elif isinstance(target,ast.Subscript) and isinstance(target.value,ast.Name) and target.value.id == 'CASES':
                    result.add(scalar(target.slice,{}))
    return result


def contract_gate(program,case,reference,contract,content_sha256,*,require_witnesses=True,draft_only=False):
    """Validate declarations against the actual compiled scenario and actors."""
    ids = fixed_roster(reference)
    if contract.get('schema') != 'ark-sim/external-model-contract/v2':
        raise ValueError('External model contract schema is required')
    if contract.get('native_level_id') != case['level_id']:
        raise ValueError('External contract belongs to a different native level')
    if program.scenario.get('metadata',{}).get('native_level_id') != case['level_id']:
        raise ValueError('Actual scenario belongs to a different native level')
    if contract.get('content_sha256') != content_sha256:
        raise ValueError('External contract belongs to different battle content')
    if contract.get('native_source_sha256') != case['native_source_sha256']:
        raise ValueError('External contract belongs to a different native source')
    if contract.get('roster_frozen_sha256') != reference['frozen_sha256']:
        raise ValueError('External contract changed the fixed roster')
    actual = [program.definitions[r].get('metadata',{}).get('native_id') for r in program.scenario.get('roster',())]
    if any(not isinstance(i,str) for i in actual) or sorted(actual) != sorted(ids):
        raise ValueError('Actual roster must contain exactly the selected twelve')
    if not isinstance(contract.get('pending_model_gaps'),list) or (contract['pending_model_gaps'] and not draft_only):
        raise ValueError('Unresolved model mechanisms remain')
    selected = contract.get('selected_skill_definitions',{})
    for row in reference['roster']:
        ref = selected.get(row['character_id'])
        if not isinstance(ref,str):
            raise ValueError('Selected skill reference must be a definition ID')
        ability = program.definitions.get(ref,{})
        unit = next(program.definitions[r] for r in program.scenario['roster']
            if program.definitions[r].get('metadata',{}).get('native_id') == row['character_id'])
        if ability.get('kind') != 'ability' or ability.get('metadata',{}).get('native_skill_id') != row['config']['skill_id']:
            raise ValueError('Selected skill is missing or substituted')
        if ref not in unit.get('components',{}).get('abilities',()):
            raise ValueError('Selected skill is not owned by its operator')
        if unit.get('metadata',{}).get('config') != row['config']:
            raise ValueError('Actual operator configuration changed')
    required = contract.get('required_mechanics')
    witnesses = contract.get('mechanic_tests',{})
    if (not isinstance(required,list) or not required or any(not isinstance(k,str) or not k for k in required)
        or len(set(required)) != len(required) or (require_witnesses and any(not witnesses.get(k) for k in required))):
        raise ValueError('Required mechanisms need explicit executed test references')
    expected = contract.get('native_spawn_by_definition')
    if not isinstance(expected,dict) or not expected or any(type(n) is not int or n <= 0 for n in expected.values()):
        raise ValueError('Native spawn population is required')
    actual_spawns = Counter()
    timeline = program.scenario.get('timeline')
    if timeline is None:
        actual_spawns.update(w['definition'] for w in program.scenario.get('waves',()))
    else:
        for wave in timeline['waves']:
            for fragment in wave['fragments']:
                for action in fragment['actions']:
                    if action['kind'] == 'spawn':
                        actual_spawns[action['spawn']['definition']] += action.get('count',1)
    if actual_spawns != Counter(expected) or sum(expected.values()) != case['expected_native_spawns']:
        raise ValueError('Actual native spawn population differs from the source contract')
    return contract


def case_identity(root,case,reference):
    from ark_sim.adapters.api import implementation_digest
    return {'content_sha256':sha(workspace_file(root,case['planned_content'])),
        'commands_sha256':sha(workspace_file(root,case['planned_commands'])),
        'contract_sha256':sha(workspace_file(root,case['planned_contract'])),
        'roster_full_sha256':object_identity(reference),
        'implementation_sha256':implementation_digest(),'native_source_sha256':case['native_source_sha256']}


def checked_artifact(root,ref):
    path = workspace_file(root,ref['path'])
    if sha(path) != ref['sha256']:
        raise ValueError('Review evidence identity changed')
    result = load(path)
    if result.get('passed') is not True:
        raise ValueError('Review evidence did not pass')
    for test in result.get('tests',[]):
        source = workspace_file(root,test['path'])
        if test.get('result') != 'passed' or sha(source) != test['source_sha256']:
            raise ValueError('Review test source is stale')
    return result


SEMANTIC_CHECKS = ('unit_attributes_and_growth','selected_skills_and_talents','native_enemy_dependencies',
    'map_routes_controls_and_objectives','no_substituted_or_ignored_mechanics')


def source_review_gate(root,references,expected):
    """Raw-value checks and semantic-consumer checks have distinct authority."""
    if not references:
        raise ValueError('Independent source reviews are required')
    covered = set()
    for reference in references:
        review = checked_artifact(root,reference)
        if review.get('schema') != 'ark-sim/source-consumer-review/v2':
            raise ValueError('Source consumer review schema is required; raw-value reports cannot approve semantics')
        if (review.get('subject_model_content_sha256') != expected['content_sha256']
            or review.get('subject_native_source_sha256') != expected['native_source_sha256']
            or review.get('implementation_sha256') != expected['implementation_sha256']):
            raise ValueError('Source review belongs to different content, native source or implementation')
        if review.get('status') != 'approved_for_declared_model_profile' or review.get('pending_model_gaps') != []:
            raise ValueError('Source review has not closed the required model consumer gaps')
        if not isinstance(review.get('reviewer'),str) or not review['reviewer'].strip():
            raise ValueError('Source semantic review needs an independent reviewer')
        locks = review.get('source_locks')
        if not isinstance(locks,list) or not locks:
            raise ValueError('Source semantic review needs actual source locks')
        for record in locks:
            path = Path(root)/record['path']
            if not path.is_file() or sha(path) != record['sha256']:
                raise ValueError('Reviewed native source lock is missing or changed')
        checks = review.get('checks',{})
        consumers = review.get('consumer_evidence',{})
        for key in SEMANTIC_CHECKS:
            if checks.get(key) == 'passed':
                evidence = consumers.get(key)
                if not isinstance(evidence,list) or not evidence:
                    raise ValueError('Semantic category lacks its actual consumer evidence')
                for item in evidence:
                    if not isinstance(item,dict) or not {'path','sha256','claim'} <= set(item) or not isinstance(item['claim'],str) or not item['claim']:
                        raise ValueError('Semantic consumer evidence must name a frozen executed artifact and its claim')
                    checked_artifact(root,item)
                covered.add(key)
        for ref in review.get('raw_source_evidence',[]):
            raw = checked_artifact(root,ref)
            if raw.get('schema') not in {'ark-sim/first-model-original-field-review/v1','ark-sim/original-source-fields-review/v2'}:
                raise ValueError('Unexpected raw source evidence schema')
    if covered != set(SEMANTIC_CHECKS):
        raise ValueError('Source semantic reviews do not cover all five required categories')
    return True


def shared_witness_gate(root,reference,receipt,expected):
    """Authorize one reviewed definition/fixture scope while retaining its run identity."""
    ref = reference.get('shared_scope_review')
    approved = {(r['path'],r['sha256']) for r in receipt.get('shared_scope_reviews',[])}
    if not isinstance(ref,dict) or (ref.get('path'),ref.get('sha256')) not in approved:
        raise ValueError('Cross-content mechanism requires an independent shared scope review')
    review = checked_artifact(root,ref)
    if (review.get('schema') != 'ark-sim/shared-mechanism-review/v2'
        or review.get('status') != 'approved_scoped_definition_use'
        or review.get('target_content_sha256') != expected['content_sha256']
        or review.get('implementation_sha256') != expected['implementation_sha256']
        or not isinstance(review.get('reviewer'),str) or not review['reviewer'].strip()):
        raise ValueError('Shared scope review is unapproved or belongs to different content/core')
    source_sha = review.get('source_content_sha256')
    if not isinstance(source_sha,str) or not source_sha or source_sha == expected['content_sha256']:
        raise ValueError('Shared scope must preserve a distinct source content identity')
    for record in review.get('source_locks',[]):
        path = Path(root)/record['path']
        if not path.is_file() or sha(path) != record['sha256']:
            raise ValueError('Shared scope source or implementation helper is stale')
    if not review.get('source_locks'):
        raise ValueError('Shared scope source locks are required')
    cases = review.get('approved_cases',[])
    matches = [c for c in cases if c.get('case') == reference.get('case')
        and c.get('source_evidence_path') == reference.get('path')
        and c.get('source_evidence_sha256') == reference.get('sha256')
        and c.get('helper_path') == reference.get('helper_path')
        and c.get('helper_sha256') == reference.get('helper_sha256')]
    if len(matches) != 1:
        raise ValueError('Mechanism case was not independently approved for this shared scope')
    record = matches[0]
    helper = workspace_file(root,record['helper_path'])
    if sha(helper) != record['helper_sha256']:
        raise ValueError('Shared mechanism helper changed')
    proof = checked_artifact(root,record['proof'])
    if (proof.get('schema') != 'ark-sim/shared-mechanism-case-proof/v2'
        or proof.get('source_content_sha256') != source_sha
        or proof.get('target_content_sha256') != expected['content_sha256']
        or proof.get('implementation_sha256') != expected['implementation_sha256']
        or proof.get('case') != reference.get('case') or proof.get('helper_sha256') != record['helper_sha256']):
        raise ValueError('Shared case proof identity does not match the reviewed mechanism')
    if proof.get('proof_type','runtime_fixture_scope') == 'static_source_definition_equivalence':
        required = ('no_runtime_fixture','static_source_assertions_equal','reachable_definitions_equal',
            'rule_and_provider_identity_equal','metadata_nonconsumption_reviewed')
        if proof.get('target_case_executed') is not False:
            raise ValueError('Static scope proof must not claim target battle execution')
    else:
        if proof.get('proof_type','runtime_fixture_scope') != 'runtime_fixture_scope':
            raise ValueError('Unknown shared mechanism proof type')
        required = ('all_fixtures_accounted_for','reachable_definitions_equal','rule_and_provider_identity_equal',
            'effective_inputs_equal','explicit_seed_equal','metadata_nonconsumption_reviewed')
    if any(proof.get(key) is not True for key in required):
        raise ValueError('Shared mechanism scope is incomplete; first fixture or zero-tick equality alone is insufficient')
    for artifact_ref in proof.get('supporting_evidence',[]):
        checked_artifact(root,artifact_ref)
    if not proof.get('supporting_evidence'):
        raise ValueError('Shared case needs frozen supporting proof evidence')
    return source_sha


def witness_gate(root,contract,receipt,expected):
    approved = {(r['path'],r['sha256']) for r in receipt['test_evidence']}
    approved.update((r['path'],r['sha256']) for r in receipt.get('stage_evidence',[]))
    for mechanism in contract['required_mechanics']:
        references = contract['mechanic_tests'][mechanism]
        if not isinstance(references,list) or not references:
            raise ValueError('Mechanism witnesses must be explicit reference lists')
        for reference in references:
            if (reference.get('path'),reference.get('sha256')) not in approved:
                raise ValueError('Mechanism witness was not reviewed with the selected inputs')
            scope_expected = expected
            if reference.get('shared_scope_review'):
                source_sha = shared_witness_gate(root,reference,receipt,expected)
                scope_expected = {**expected,'content_sha256':source_sha}
            if reference.get('witness_kind') == 'completed_stage':
                from ark_sim import Compiler
                run = checked_artifact(root,reference)
                program = Compiler().compile(workspace_file(root,receipt['stage_content_path']))
                commands = load(workspace_file(root,receipt['stage_commands_path']))
                completed_stage_gate(program,contract,expected,run,commands)
            elif reference.get('witness_kind') == 'full_suite_source_node':
                evidence = checked_artifact(root,reference)
                if evidence.get('schema') != 'ark-sim/campaign-test-evidence/v1':
                    raise ValueError('Source-node witness needs a completed full-suite artifact')
                node = reference.get('test_node_id','')
                parts = node.split('::')
                if len(parts) != 2:
                    raise ValueError('Explicit test node is required')
                path,name = parts;function = name.split('[',1)[0]
                sources = {r['path']:r['source_sha256'] for r in evidence['tests']}
                if sources.get(path) != reference.get('test_source_sha256'):
                    raise ValueError('Mechanism node source was not in the executed suite')
                tree = ast.parse(workspace_file(root,path).read_bytes())
                functions = {n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
                if function not in functions:
                    raise ValueError('Mechanism test function does not exist')
                if '[' in name:
                    if name.count('[') != 1 or not name.endswith(']'):
                        raise ValueError('Malformed parameterized test node')
                    case = name.split('[',1)[1].removesuffix(']')
                    helper = workspace_file(root,reference['helper_path'])
                    helper_module = reference['helper_path'].removesuffix('.py').replace('/','.')
                    imports_cases = any(isinstance(n,ast.ImportFrom) and n.module == helper_module
                        and any(i.name == 'CASES' for i in n.names) for n in tree.body)
                    decorators = functions[function].decorator_list
                    uses_cases = any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                        and n.func.attr == 'parametrize' and len(n.args) >= 2
                        and isinstance(n.args[1],ast.Call) and isinstance(n.args[1].func,ast.Name)
                        and n.args[1].func.id == 'list' and len(n.args[1].args) == 1
                        and isinstance(n.args[1].args[0],ast.Name) and n.args[1].args[0].id == 'CASES'
                        for n in decorators)
                    if not imports_cases or not uses_cases:
                        raise ValueError('Test parameter collection does not use the locked helper cases')
                    dependencies = {r['path']:r['source_sha256'] for r in evidence['dependency_sources_verified']}
                    if dependencies.get(reference['helper_path']) != reference['helper_sha256'] or sha(helper) != reference['helper_sha256']:
                        raise ValueError('Parameterized mechanism helper was not locked by the executed suite')
                    helper_tree = ast.parse(helper.read_bytes())
                    keys = source_case_keys(helper_tree)
                    if case not in keys:
                        raise ValueError('Mechanism parameter is absent from the exact source case collection: '+reference['helper_path']+' / '+case)
                execution = checked_artifact(root,{'path':evidence['source_execution_artifact'],'sha256':evidence['source_execution_sha256']})
                if execution['input_package_sha256'] != scope_expected['content_sha256']:
                    raise ValueError('Full-suite package differs from battle content')
                launch = checked_artifact(root,receipt['suite_launch_provenance'])
                if launch.get('environment_assignments_verified_from_actual_launch') is not True:
                    raise ValueError('Full-suite launch environment lacks authoritative provenance')
                for key in ('CAMPAIGN_MECHANISM_PACKAGE','CAMPAIGN_SUMMON_PACKAGE'):
                    if sha(workspace_file(root,launch['environment'][key])) != scope_expected['content_sha256']:
                        raise ValueError('Full-suite actual launch used different content')
            else:
                resolve_case(root,reference,scope_expected['implementation_sha256'],scope_expected['content_sha256'])


def review_gate(root,case,reference,receipt_path):
    """Contract flags cannot replace an independent review bound to every input."""
    from ark_sim import Compiler
    receipt = load(workspace_file(root,receipt_path))
    expected = case_identity(root,case,reference)
    if (receipt.get('schema') != 'ark-sim/external-model-review/v2'
        or receipt.get('status') != 'approved_for_model_run'
        or receipt.get('native_id') != case['native_id']
        or receipt.get('input_identity') != expected or not isinstance(receipt.get('reviewer'),str) or not receipt['reviewer'].strip()):
        raise ValueError('Independent model review is missing, incomplete or stale')
    checks = SEMANTIC_CHECKS
    if any(receipt.get('checks',{}).get(k) != 'passed' for k in checks):
        raise ValueError('Independent semantic review checks are incomplete')
    source_reviews = receipt.get('source_reviews',[])
    test_evidence = receipt.get('test_evidence',[])
    if not source_reviews or not test_evidence:
        raise ValueError('Independent source and executed test evidence are required')
    source_review_gate(root,source_reviews,expected)
    for ref in test_evidence:
        artifact = checked_artifact(root,ref)
        if artifact.get('implementation_sha256') != expected['implementation_sha256'] or not artifact.get('tests'):
            raise ValueError('Executed tests belong to a different implementation or lack source identity')
    contract = load(workspace_file(root,case['planned_contract']))
    program = Compiler().compile(workspace_file(root,case['planned_content']))
    contract_gate(program,case,reference,contract,expected['content_sha256'])
    witness_gate(root,contract,receipt,expected)
    return receipt,expected,contract,program


def consume_completed_stage(root,case,reference,receipt_path,run_reference):
    """Accept a completed same-input three-way run, without changing its identity."""
    receipt,expected,contract,program = review_gate(root,case,reference,receipt_path)
    run = checked_artifact(root,run_reference)
    commands = load(workspace_file(root,case['planned_commands']))
    completed_stage_gate(program,contract,expected,run,commands)
    return {'schema':'ark-sim/accepted-model-result/v2','native_id':case['native_id'],
        'model_status':'accepted','client_status':'pending','input_identity':expected,
        'program_fingerprint':program.fingerprint,'runtime_fingerprint':run['runtime_fingerprint'],
        'conversion_review_sha256':sha(workspace_file(root,receipt_path)),
        'completed_run':dict(run_reference),'observations':run['observations'],'model_result':run['state'],
        'checkpoint_equal':True,'replay_equal':True,'reviewer':receipt['reviewer'],
        'scope':'Declared model/profile only; client validation stays separate'}


def completed_stage_gate(program,contract,expected,run,commands):
    """Check whole-stage observations independently of approval/receipt presence."""
    from ark_sim import Engine
    if run.get('passed') is not True:
        raise ValueError('Completed stage did not finish successfully')
    if run.get('schema') != 'ark-sim/partial-stage-model-validation/v1':
        raise ValueError('Unsupported completed stage evidence schema')
    if run.get('package_sha256') != expected['content_sha256'] or run.get('commands_sha256') != expected['commands_sha256']:
        raise ValueError('Completed battle belongs to different content or commands')
    if run.get('checkpoint_resume_equal') is not True or run.get('replay_equal') is not True:
        raise ValueError('Full checkpoint and command replay equality are required')
    sim = Engine.create(program,seed=run['model_seed'])
    if run.get('program_fingerprint') != program.fingerprint or run.get('runtime_fingerprint') != sim.runtime_fingerprint:
        raise ValueError('Completed battle belongs to a different program/runtime identity')
    state = run.get('state',{})
    if not state.get('finished') or state.get('result') != 'victory' or state.get('pending_waves') or state.get('leaks'):
        raise ValueError('Complete no-leak victory is required')
    spawned = run.get('spawned_by_definition',{})
    if spawned != contract['native_spawn_by_definition']:
        raise ValueError('Completed run did not preserve declared spawn population')
    if (type(state.get('kills')) is not int or type(state.get('leaks')) is not int
        or state['kills'] + state['leaks'] != sum(spawned.values())):
        raise ValueError('Enemy lifecycle conservation differs')
    observed = run.get('observed_commands',[])
    if len(observed) != len(commands) or any(e['type'] != 'command.accepted' for e in observed):
        raise ValueError('All scripted commands must have been executed legally')
    if not run.get('observations',{}).get('state_sha256') or not run.get('observations',{}).get('events_sha256'):
        raise ValueError('Whole-snapshot and event observations are required')
    return True
