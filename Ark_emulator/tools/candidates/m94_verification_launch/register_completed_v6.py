import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    launch=json.loads((ROOT/'validation/campaign/m94_complete_c4/runthrough_launch.m96_v6.named.prepared.json').read_bytes())
    native=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate/stage/level_main_04-09.m96.first_hit.source_circle.native_life.json'
    copies={Path(launch['package']):ROOT/'packages/campaign/runthrough/level_main_04-09.m96.v6.life99999.json',
        native:ROOT/'packages/campaign/chapter04_stage_models/level_main_04-09.m96.reference_model.json',
        Path(launch['commands']):ROOT/'scenarios/campaign/chapter04/04-09/commands.public_v6.json'}
    for source,target in copies.items():
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert sha(target)==sha(source)
        else:
            with target.open('xb') as f:f.write(source.read_bytes())
        assert sha(target)==sha(source)
    entry={'package':str(copies[Path(launch['package'])].relative_to(ROOT)),
        'parent_package':str(copies[native].relative_to(ROOT)),'parent_sha256':sha(native),
        'commands':str(copies[Path(launch['commands'])].relative_to(ROOT)),
        'implementation':launch['core'],'report':'validation/campaign/m94_complete_c4/full49_m96_v6.json',
        'input_validation':'native_life_overlay_v1'}
    from tools.campaign_runthrough_progress_v3 import inspect
    result=inspect(ROOT,entry)
    assert result['process_status']=='complete' and result['determinism_status']=='verified' and result['durable_checkpoint_status']=='verified',result
    target=ROOT/'validation/campaign/m94_complete_c4/root_v6_registration_inspect.json'
    with target.open('x',encoding='utf8') as f:json.dump({'entry':entry,'inspection':result,'copied_bytes_equal':True},f,indent=2)
    path=ROOT/'validation/campaign/runthrough/registry.json';registry=json.loads(path.read_bytes())
    assert 'main_04-09' not in registry['cases'];registry['cases']['main_04-09']=entry
    path.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'registered':'main_04-09','inspection':result,'receipt_sha':sha(target)}))
if __name__=='__main__':main()
