"""Run current M68 primary/isolated suites after promotion; preserve old runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
CORE='1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();runtime=args.runtime_root.resolve()
    if args.output.exists():raise ValueError('Preserve existing suite reports; choose a fresh output')
    sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim' and implementation_digest()==CORE
    os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
    os.environ['ARKSIM_M10_REVIEW_ROOT']=str(runtime)
    selection=['tests_v2',
        *['tools/experiments/m38/'+name for name in ('test_storage.py','test_refs.py','test_fields.py','test_static_owner.py','test_overrides.py','test_board_scope.py','test_role.py')],
        'tools/experiments/m68_integration','--ignore=tools/experiments/m68_integration/test_rules_catalog.py',
        'tools/experiments/m26_content/test_composition.py',
        'tools/experiments/m23','tools/experiments/chapter02_tiles']
    paths=[Path(__file__),runtime/'ark_sim/rules/contracts.json',runtime/'ark_sim/content/presets/ark_standard.json',
        Path(os.environ['CAMPAIGN_SUMMON_PACKAGE'])]
    for name in selection:
        if name.startswith('--'):continue
        path=ROOT/name
        paths.extend(path.rglob('*.py') if path.is_dir() else [path])
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before=guard();code=int(pytest.main([*selection,'-q','--tb=short']));after=guard()
    result={'passed':code==0 and before==after and implementation_digest()==CORE,'exit_code':code,
        'core_start':CORE,'core_end':implementation_digest(),'actual_module':ark_sim.__file__,
        'source_start':before,'source_end':after,'selection':selection,'actual_client_verified':False,
        'scope':'Current selected test source under explicit M68 runtime; old full-suite evidence unchanged'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
