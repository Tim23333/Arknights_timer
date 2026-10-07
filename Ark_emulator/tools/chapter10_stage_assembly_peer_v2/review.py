"""Typed successor-input review; tool scopes are separate from core approval."""
import sys,json,copy,hashlib,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter10_stage_source_peer_v1.source_preflight import exact
PARENT=ROOT/'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v2.life99999.json'
NEW=ROOT/'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v3.life99999.json'
FREEZE=ROOT/'validation/campaign/campaign_elemental_lease_v4/freeze.functional.v4.json'
RECEIPT=ROOT/'validation/campaign/chapter10_stage_assembly_v2/source.successor94d2.v1.json'
OUT=ROOT/'validation/campaign/chapter10_stage_assembly_peer_v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_bytes())
def main():
    tools=[ROOT/'tools/chapter10_stage_assembly_v2'/f for f in ['prepare_successor.py','verify_prefix_v3.py','verify_baseline.py']]
    inputs=[PARENT,NEW,FREEZE,RECEIPT,Path(__file__),ROOT/'tools/verify_v2_baseline.py',*tools];before={str(p):sha(p) for p in inputs}
    assert sha(PARENT)=='7afc5aa0b3ef49d1333b788aa78e464460e68072ff57e0086607eae8949cccee'
    assert sha(NEW)=='afe76e816d71cfeb8fad44dc31ad5168705c0f67940608051758e4991ef346e9'
    old=load(PARENT);new=load(NEW);freeze=load(FREEZE);meta=new['manifest']['metadata'];core=freeze['core'];runtime=Path(freeze['candidate'])
    assert core=='94d2f5cfcc42f8845c6cb23643f1910aa94a78115a60d83813d0738df6db8c63' and meta['required_runtime']==core
    pins={k:sha(runtime/k) for k in freeze['source_inventory']};exact(pins,freeze['source_inventory'])
    restored=copy.deepcopy(new);restored['manifest']['metadata']['required_runtime']=old['manifest']['metadata']['required_runtime'];binding=restored['manifest']['metadata'].pop('successor_source_binding');exact(restored,old)
    exact(old['definitions'],new['definitions']);exact(old['scenarioDraft'],new['scenarioDraft'])
    assert binding['parent_sha256']==sha(PARENT) and binding['successor_runtime']==core and binding['parent_runtime']==old['manifest']['metadata']['required_runtime']
    assert binding['battle_inputs_changed'] is False and binding['runtime_validation_pending'] is True and binding['whole_stage_executed'] is False and binding['client_verified'] is False
    assert sha(Path(binding['source_review']))==binding['source_review_sha256']=='ee5509ec8b05ee0aae018109ce89bf8c913daa87d8789fd1fffe2e095a092982'
    for path,value in meta['source_locks'].items():assert sha(Path(path))==value,path
    exact(old['manifest']['metadata']['source_locks'],meta['source_locks'])
    sys.path.insert(0,str(runtime))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter10_stage_assembly_v1.providers import providers
    assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim' and implementation_digest()==core
    program=Compiler(providers=providers()).compile(new);receipt=load(RECEIPT);assert program.fingerprint==receipt['program'] and receipt['output_sha256']==sha(NEW)
    for tool in tools:ast.parse(tool.read_text(encoding='utf8'))
    prefix=tools[1].read_text(encoding='utf8');baseline=tools[2].read_text(encoding='utf8');prepare=tools[0].read_text(encoding='utf8')
    assert "Path(ark_sim.__file__).resolve().parent" in prefix and "is_relative_to(runtime / 'ark_sim')" in prefix
    assert 'continuous.checkpoint() == staged.checkpoint() == head.checkpoint()' in prefix and 'list(continuous.session.events) == list(staged.session.events) == list(head.session.events)' in prefix
    assert "Path(ark_sim.__file__).resolve().parent" in baseline and "is_relative_to(runtime / 'ark_sim')" in baseline
    after={str(p):sha(p) for p in inputs};assert before==after
    report={'schema':'ark-sim/independent-successor-source-review/v1','source_input_approved':True,'actual_compile':True,'simulation_created':False,'model_approved':False,'core_approved':False,'whole_stage_approved':False,'client_verified':False,'source_before':before,'source_after':after,'source_equal':True,'actual_runtime_module':ark_sim.__file__,'actual_core':implementation_digest(),'actual_program':program.fingerprint,'runtime_freeze_inventory_current':len(pins),'typed_equality':{'all_original_definitions':len(new['definitions']),'all_scenario_fields':True,'entire_package_after_exactly_two_metadata_changes':True,'old_source_locks_preserved_current':len(meta['source_locks'])},'tool_review':{'prepare':'Actual import/core path bound, original review/package/source hashes checked; changes only metadata; fresh compile, runtime gate remains pending.','prefix_v3':'Actual loaded root and all ark_sim module paths bound. Full checkpoint and full event arrays compare uninterrupted/staged149,151,599,600/head601. Only first2 publiccommands/prefix scope; not whole stage.','baseline':'Actual root/all ark_sim module paths bound; original custom850/60 and 0-1 process/CPP/head observations contract. Existing helper observations omit attribute_cache, so not full-cache checkpoint equality.','baseline_known_tool_failure':'Original helper final replay_path.relative_to(ROOT) metadata fails for fixed E output, actual baseline.tool9a.v1 false retained. New correction must be explicit and preserve failures; this review does not approve that failed run.'},'prior_actual_tool_failures':[{'path':str(ROOT/'validation/campaign/chapter10_stage_assembly_v2/public.prefix601.94d2.v1.json'),'meaning':'str passed into Path-only sha before simulation; old report preserved, current v3 fixed.'},{'path':str(ROOT/'validation/campaign/chapter10_stage_assembly_v2/baseline.tool9a.v1.json'),'meaning':'E replay metadata path cannot relative_to D root after compare; actual overall failure preserved.'}],'pending':['Functional94d2 independent/full/baseline runtime gates','Actual prefix outcomes under current tool','Original full41 publiccommands/whole process/CPP/head','Client source-method/timing parity']}
    OUT.mkdir(parents=True,exist_ok=True);file=OUT/'source.review.v1.json';assert not file.exists();file.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'source_input_approved':True,'sha256':sha(file),'core_approved':False,'whole_approved':False}))
if __name__=='__main__':main()
