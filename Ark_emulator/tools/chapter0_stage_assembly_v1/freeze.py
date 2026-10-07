"""Freeze completed author source/input/prefix material without whole admission."""
import hashlib,json,copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;OUT=ROOT/'validation/campaign/chapter0_stage_assembly_v1';PACK=ROOT/'packages/campaign/chapter0_stage_models'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    result=json.loads((OUT/'prefix.actual.v4.json').read_bytes());assert result['passed'] and result['source_unchanged'] and len(result['cases'])==2
    assert result['core']=='08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878'
    assert all(c['four_observations_equal'] and c['full_checkpoint_equal'] and c['driver_CP_head_equal'] for c in result['cases'])
    assert all(sha(p)==h for p,h in result['source_guards'].items())
    for v in (1,2,3,4):
        path=Path(f'E:/ArkSimLogs/receipts/chapter0_stage_prefix_20261007_v{v}/completion.json');done=json.loads(path.read_bytes());assert done['worker_exit']==(1 if v<3 else 0) and done['cleanup_exit']==0 and done['raw_logs_removed_after_validation'] and done['cleanup_result']['fully_cleaned'];(OUT/f'completion.v{v}.json').write_bytes(path.read_bytes())
    packages={str(p.relative_to(ROOT)):sha(p) for p in PACK.glob('*.source.v2.json')};plans={str(p.relative_to(ROOT)):sha(p) for p in PACK.glob('*.public.plan.v5.json')};assert len(packages)==len(plans)==2
    sys.path.insert(0,str(ROOT));from ark_sim import Compiler
    identity=[]
    for stage in ('level_main_00-10','level_main_00-11'):
        old=json.loads((PACK/(stage+'.public.plan.v4.json')).read_bytes());new=json.loads((PACK/(stage+'.public.plan.v5.json')).read_bytes());assert old['commands']==new['commands'] and new['manual_selected_skill_attempts']==50
        raw=json.loads((PACK/(stage+'.source.v2.json')).read_bytes());programs=[]
        for plan in (old,new):
            p=copy.deepcopy(raw);p['scenarioDraft']['commands']=copy.deepcopy(plan['commands']);first=next(c for c in plan['commands'] if c['action']=='deploy');reject=copy.deepcopy(first);reject['at']=2;reject['alias']='blocked-input-probe';p['scenarioDraft']['commands'].insert(0,reject);programs.append(Compiler().compile(p).fingerprint)
        assert programs[0]==programs[1];identity.append({'stage':stage,'actual_prefix_bound_plan':'public.plan.v4','final_plan':'public.plan.v5','commands_equal':True,'compiled_program_fingerprints':programs,'metadata_count_correction_only':'v4 incorrectly declared52 selected attempts; actual commands are50 selected +3 summons, corrected without command or runtime changes'})
    for path in packages:
        p=json.loads((ROOT/path).read_bytes());assert all(sha(k)==h for k,h in p['manifest']['metadata']['source_locks'].items())
    record={'schema':'ark-sim/chapter0-source-assembly-functional-freeze/v2','core':result['core'],'source_packages':packages,'public_plans':plans,'tools':{str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.is_file()},'reports':{str(p.relative_to(ROOT)):sha(p) for p in OUT.glob('*.json') if p.name!='freeze.functional.v2.json'},
      'author_source_and_typed_input_passed':True,'actual_public_prefix_passed':True,'full_disk_CP_head_and_driver_equal':True,'end_tick':180,'source_births':[35,37],'roster_count':12,'summon_bodies':3,
      'final_plan_metadata_correction_program_identity':identity,'native_UI_pause_and_dwell_verified':False,'native_method_bodies_verified':False,'third_party_review_pending':True,'queue_ready':False,'whole_stage_started':False,'whole_stage_passed':False,'client_verified':False,'existing_live_runs_modified':False}
    path=OUT/'freeze.functional.v2.json';path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha256':sha(path),'queue_ready':False,'whole_stage':False}))
if __name__=='__main__':main()
