"""Save exact current join preparation inputs without upgrading partial claims."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    rels=['tools/chapter06_review/stage_converter_v6.py','tools/chapter06_review/verify_converter_v6_sources.py',
        'tools/chapter06_review/verify_converter_v6_control_runtime.py','tools/chapter06_review/build_join_inventory_v7.py',
        'tools/chapter06_npcs/providers_v2.py','tools/chapter06_npcs/huang_v6_policy.py','tools/chapter06_npcs/amiya_policy.py','tools/chapter06_npcs/policies.py',
        'packages/campaign/chapter06_npcs/huang.v7.model.json','packages/campaign/chapter06_npcs/huang_talents.v7.model.json',
        'validation/campaign/chapter06_join_inventory_v7/inventory.json',
        'validation/campaign/chapter06_converter_v6_sources_strict/verification.json',
        'validation/campaign/chapter06_converter_v6_control_runtime/verification.json',
        'validation/campaign/chapter06_npcs_author_v2/freeze.json','validation/campaign/chapter06_static_selfremove_v1/freeze.json']
    runtime=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate/ark_sim'
    paths=[ROOT/p for p in rels]+[Path(__file__)]+[p for p in runtime.rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts]
    files={str(p):sha(p) for p in paths}
    out=ROOT/'validation/campaign/chapter06_join_preparation_v1';out.mkdir(exist_ok=False)
    target=out/'freeze.json';target.write_text(json.dumps({'files':files,
        'core':'fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b',
        'scope':'Current source converter, combined compile and partial controls execution only; independent review/fullcore/fullstage still pending. Each original proof retains recorded runtime and source identity.',
        'ordinary_boss_not_finalized':True,'story_boss_missing':True,'formal_approval':False},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'files':len(files),'sha':sha(target)}))


if __name__=='__main__':main()
