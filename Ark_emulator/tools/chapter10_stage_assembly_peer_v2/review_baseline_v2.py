"""Static faithful-delta audit of new baseline helper, no simulation."""
import json,hashlib,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter10_stage_assembly_peer_v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    old=ROOT/'tools/verify_v2_baseline.py';helper=ROOT/'tools/chapter10_stage_assembly_v2/baseline_helper_v2.py';wrapper=ROOT/'tools/chapter10_stage_assembly_v2/verify_baseline_v2.py';source_review=OUT/'source.review.v1.json'
    paths=[old,helper,wrapper,source_review,Path(__file__)];before={str(p):sha(p) for p in paths}
    previous=json.loads(source_review.read_bytes());assert previous['source_input_approved'] and all(sha(Path(p))==h for p,h in previous['source_after'].items())
    expected=old.read_text(encoding='utf8').replace('ROOT = Path(__file__).resolve().parents[1]','ROOT = Path(__file__).resolve().parents[2]')
    expected=expected.replace('        "program_fingerprint": simulation.program.fingerprint,\n        "runtime_fingerprint": simulation.runtime_fingerprint,\n','        "program_fingerprint": simulation.program.fingerprint,\n        "runtime_fingerprint": simulation.runtime_fingerprint,\n        "attribute_cache": simulation.ctx.attributes.checkpoint_cache(),\n        "commands": simulation._commands,\n')
    expected=expected.replace('str(replay_path.relative_to(ROOT)).replace("\\\\", "/")','str(replay_path.resolve())')
    assert helper.read_text(encoding='utf8')==expected,'Any additional helper edits require independent review'
    source=wrapper.read_text(encoding='utf8');ast.parse(source);ast.parse(expected)
    assert 'baseline_helper_v2 as baseline' in source and "Path(ark_sim.__file__).resolve().parent" in source and "is_relative_to(runtime / 'ark_sim')" in source
    assert 'except Exception:' in source and "proof['error'] = traceback.format_exc()" in source and "proof['passed'] &= proof['identity_stable']" in source
    after={str(p):sha(p) for p in paths};assert before==after
    report={'schema':'ark-sim/baseline-helper-static-delta-review/v2','tool_scope_approved':True,'source_input_review_unchanged':True,'source_before':before,'source_after':after,'source_equal':True,'allowed_exact_changes':['ROOT directory depth adjusted for new helper location','Replay metadata records actual absolute E path','Attribute-cache state added to strict state digest','Actual public command ledger added to strict state digest'],'validation_comparisons_removed':False,'old_assertions_byte_preserved':True,'actual_runtime_root_and_all_module_paths_checked':True,'failure_not_caught_as_pass':True,'baseline_execution_result_approved':False,'core_or_model_approved':False,'whole_stage_approved':False,'simulation_started':False,'scope':'Static tool delta only. New actual baseline results and cleanup receipt remain required. Original failed baseline report untouched.'}
    path=OUT/'baseline.tool.review.v2.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'tool_scope_approved':True,'sha256':sha(path)}))
if __name__=='__main__':main()
