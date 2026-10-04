"""Build shared-mechanism scope proposals without executing or relabeling cases."""
import argparse
import ast
from collections import Counter
from copy import deepcopy
import importlib
import inspect
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.prepare_external_00_11 import SOURCE,PIN,CORE
from tools.build_first_model_conversion import INPUT as BASELINE,INPUT_SHA as BASELINE_SHA,read,sha,identity,require,write,relative


class CapturedFixture(Exception):
    def __init__(self,data,seed):self.data=deepcopy(data);self.seed=seed
class UncapturedEngine(Exception):pass


MODULES=['witness_deployed_six','witness_deployed_offensive','witness_deployed_support','witness_canonical_roster_trio',
    'canonical_summon_witness_support','witness_canonical_lisk_defense','witness_canonical_night','witness_canonical_weedy',
    'witness_canonical_kalts','witness_kalts_boundaries','witness_angel_blessing_damage']


def capture(modules,fn,package):
    """Stop at real fixture-to-Engine boundary; never return a fake simulation."""
    from ark_sim import Engine
    changed=[];create=Engine.__dict__['create']
    def forbid_engine(*args,**kwargs):raise UncapturedEngine('case bypassed declared make; no execution performed')
    Engine.create=staticmethod(forbid_engine)
    try:
        for m in modules:
            if hasattr(m,'PACKAGE'):changed.append((m,'PACKAGE',m.PACKAGE));m.PACKAGE=package
            if hasattr(m,'make') and callable(m.make):
                original=m.make;changed.append((m,'make',original));signature=inspect.signature(original)
                def recorder(*args,_signature=signature,**kwargs):
                    bound=_signature.bind(*args,**kwargs);bound.apply_defaults()
                    data=bound.arguments.get('data',next(iter(bound.arguments.values())))
                    raise CapturedFixture(data,bound.arguments.get('seed',11))
                m.make=recorder
        try:return_value=fn()
        except CapturedFixture as result:return result
        except UncapturedEngine as error:return {'status':'uncaptured','reason':str(error)}
        return {'status':'source_config_only','reason':'function returned without make; do not claim fixture capture','actual_static_result':return_value}
    finally:
        Engine.create=create
        for m,key,value in reversed(changed):setattr(m,key,value)


def evaluate(a,b):
    from ark_sim import Compiler,Engine
    from ark_sim.contracts import thaw
    pa,pb=Compiler().compile(a.data),Compiler().compile(b.data)
    require(a.seed==b.seed,'explicit helper seed changed')
    dependencies_equal=set(pa.dependency_ids)==set(pb.dependency_ids)
    mismatches=[i for i in sorted(set(pa.dependency_ids)&set(pb.dependency_ids)) if pa.definitions[i]!=pb.definitions[i] and pa.definitions[i]['kind']!='scenario']
    scenario_changes=[key for key in sorted(set(pa.scenario)|set(pb.scenario)) if pa.scenario.get(key)!=pb.scenario.get(key)]
    allowed={'metadata','seed'}
    # Seed is actually passed by the locked make function; caller-native scene
    # seed is retained as a compiler/identity difference, never renamed actual.
    effective_a=thaw(pa.scenario);effective_b=thaw(pb.scenario)
    effective_a.pop('metadata',None);effective_b.pop('metadata',None)
    effective_a['seed']=a.seed;effective_b['seed']=b.seed
    effective_equal=effective_a==effective_b
    sa,sb=Engine.create(pa,seed=a.seed),Engine.create(pb,seed=b.seed)
    providers_a={n:thaw(v[2]) for n,v in sa.ctx.rules.providers.items()};providers_b={n:thaw(v[2]) for n,v in sb.ctx.rules.providers.items()}
    rule_equal=sa.ctx.rules.fingerprint==sb.ctx.rules.fingerprint
    initial_world_equal=sa.session.world.snapshot()==sb.session.world.snapshot()
    initial_events_equal=sa.session.events==sb.session.events
    initial_rng_equal=sa.session.random.snapshot()==sb.session.random.snapshot()
    source_anchor=a.data.get('manifest',{}).get('metadata',{}).get('dependency_source',{}).get('native_level_sha256')
    target_anchor=b.data.get('manifest',{}).get('metadata',{}).get('dependency_source',{}).get('native_level_sha256')
    loader_verified=source_anchor==read(BASELINE)['manifest']['metadata']['dependency_source']['native_level_sha256'] and target_anchor==read(SOURCE)['manifest']['metadata']['dependency_source']['native_level_sha256']
    structural=loader_verified and dependencies_equal and not mismatches and effective_equal and set(scenario_changes)<=allowed and rule_equal and providers_a==providers_b and initial_world_equal and initial_events_equal and initial_rng_equal
    return {'structural_equivalence_candidate':structural,'source_program_fingerprint':pa.fingerprint,'target_program_fingerprint':pb.fingerprint,
        'source_runtime_fingerprint':sa.runtime_fingerprint,'target_runtime_fingerprint':sb.runtime_fingerprint,
        'explicit_helper_seed':a.seed,'source_scenario_seed':pa.scenario.get('seed'),'target_scenario_seed':pb.scenario.get('seed'),
        'scenario_changed_keys':scenario_changes,'metadata_not_blanket_ignored':True,
        'effective_scenario_inputs_sha256':identity(effective_a),'effective_scenario_inputs_equal':effective_equal,
        'dependency_id_sets_equal':dependencies_equal,'changed_reachable_definitions':mismatches,
        'reachable_definition_identities':[{'id':i,'sha256':identity(pa.definitions[i])} for i in sorted(pa.dependency_ids) if pa.definitions[i]['kind']!='scenario'],
        'source_rule_fingerprint':sa.ctx.rules.fingerprint,'target_rule_fingerprint':sb.ctx.rules.fingerprint,
        'provider_descriptors_equal':providers_a==providers_b,'provider_descriptors':providers_a,
        'actual_package_loader_anchors_verified':loader_verified,'source_loader_anchor':source_anchor,'target_loader_anchor':target_anchor,
        'initial_world_equal':initial_world_equal,'initial_events_equal':initial_events_equal,'initial_rng_equal':initial_rng_equal,
        'source_fixture_package_sha256':identity(a.data),'target_fixture_package_sha256':identity(b.data),
        'source_fixture_scenario':thaw(pa.scenario),'target_fixture_scenario':thaw(pb.scenario),
        'proof_limit':'No case battle execution; only first fixture captured. Immutable metadata/seed identity differences require independent review of non-consumption; source reports remain0fb.'}


def build():
    from ark_sim.adapters.api import implementation_digest
    require(implementation_digest()==CORE and sha(BASELINE)==BASELINE_SHA and sha(SOURCE)==PIN,'input/core changed')
    modules=[importlib.import_module('tools.'+name) for name in MODULES]
    identity_paths=[Path(m.__file__) for m in modules]+[Path(__file__),BASELINE,SOURCE]
    source_hashes={relative(p):sha(p) for p in identity_paths}
    rows=[]
    a_source,b_source=read(BASELINE),read(SOURCE)
    source_squad=a_source['manifest']['metadata']['squad_model'];target_squad=b_source['manifest']['metadata']['squad_model']
    require(source_squad==target_squad,'source ingredient package/config integration changed')
    ingredient_locks=[]
    for name,digest in source_squad['source_packages'].items():
        path=ROOT/'packages/campaign'/('skills.'+name+'.json');require(sha(path)==digest,'recipe source identity changed');ingredient_locks.append({'path':relative(path),'sha256':digest})
    for name,digest in source_squad['talent_source_packages'].items():
        path=ROOT/'packages/campaign'/('talents.'+name+'.json');require(sha(path)==digest,'talent source identity changed');ingredient_locks.append({'path':relative(path),'sha256':digest})
    base_path=ROOT/'packages/campaign/units.base.json';require(sha(base_path)==source_squad['base_model_sha256'],'base unit source changed');ingredient_locks.append({'path':relative(base_path),'sha256':sha(base_path)})
    for m in modules:
        cases=getattr(m,'CASES',None)
        if cases is None:
            cases={'probe':m.probe} if m.__name__.endswith('witness_canonical_lisk_defense') else {'friend_damage_capacity_source_exit':m.run} if m.__name__.endswith('witness_angel_blessing_damage') else {}
        for case,fn in cases.items():
            row={'helper_path':relative(Path(m.__file__)),'helper_sha256':source_hashes[relative(Path(m.__file__))],'case':case,
                'source_content_sha256':BASELINE_SHA,'target_content_sha256':PIN,'formal_approval':False,'target_case_executed':False}
            a,b=capture(modules,fn,BASELINE),capture(modules,fn,SOURCE)
            if not isinstance(a,CapturedFixture) or not isinstance(b,CapturedFixture):
                row.update(status='not_a_fixture_proof',source_capture=a if isinstance(a,dict) else 'captured',target_capture=b if isinstance(b,dict) else 'captured',
                    criterion='Static config/source case requires separate12config/source-asset proof; no make capture is claimed')
                if isinstance(a,dict) and isinstance(b,dict) and a.get('status')==b.get('status')=='source_config_only':
                    row['static_source_results_equal']=a['actual_static_result']==b['actual_static_result']
            else:
                try:result=evaluate(a,b)
                except Exception as error:row.update(status='proposal_rejected',reason=repr(error))
                else:row.update(status='structural_candidate_requires_review' if result['structural_equivalence_candidate'] else 'shared_scope_rejected',proof=result)
            source=inspect.getsource(fn)
            try:tree=ast.parse(__import__('textwrap').dedent(source))
            except SyntaxError:row['literal_make_call_sites_in_entry']='lambda forwarding: first capture only; reviewer must inspect target function'
            else:row['literal_make_call_sites_in_entry']=sum(isinstance(n,ast.Call) and ((isinstance(n.func,ast.Attribute) and n.func.attr=='make') or (isinstance(n.func,ast.Name) and n.func.id=='make')) for n in ast.walk(tree))
            if isinstance(row['literal_make_call_sites_in_entry'],int) and row['literal_make_call_sites_in_entry']>1:
                row['status']='multi_fixture_scope_not_proven';row['criterion']='Only first make captured; later distinct scenario remains unproven. No all-case sharing approval.'
            rows.append(row)
    require(source_hashes=={relative(p):sha(p) for p in identity_paths} and implementation_digest()==CORE,'helper/input/core changed')
    return {'schema':'ark-sim/shared-mechanism-scope-proposal/v1','status':'unapproved_structural_proposal','formal_approval':False,'passed':True,
        'implementation_sha256':CORE,'source_content_sha256':BASELINE_SHA,'target_content_sha256':PIN,
        'source_at_start':source_hashes,'source_at_completion':source_hashes,'identity_stable':True,'case_proposals':rows,
        'static_config_source_proof':{'source_and_target_squad_ingredients_equal':True,'ingredient_actual_sha_locks':ingredient_locks,
            'meaning':'Same12configs/operator/template/source assets; four source-only functions ran assertions and returned without make. No simulation or fixture capture is claimed.'},
        'method':'Sentinel stops real helper at make; no fake Simulation and no case run. Actual zero-tick Engine initialization compares effective inputs/reachable definitions/rules/providers/world/events/RNG.',
        'default_cross_package_gate_must_still_reject':True,'source_report_input_hashes_not_modified':True,
        'reviewer_requirements':['verify metadata is not a rule/provider/helper math input for each proposed case','verify explicit Engine seed override and all other scenario inputs','reject changed native enemy dependencies','prove all fixtures for multi-scenario cases','independently approve scoped use; never claim target case executed']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'packages/campaign/conversion_drafts/main_00-11.witness_scope.proposal.json');parser.add_argument('--check',action='store_true');args=parser.parse_args();value=build()
    if args.check:require(args.output.exists() and read(args.output)==value,'scope proposal drift')
    else:write(args.output,value)
    counts=Counter(r['status'] for r in value['case_proposals'])
    print(json.dumps({'proposal_cases':len(value['case_proposals']),'status_counts':counts,'formal_approval':False}))


if __name__=='__main__':
    main()
