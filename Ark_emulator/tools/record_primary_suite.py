"""Record a completed primary-suite log and its current source inventory."""
import argparse
import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_mechanism_evidence import sha


def source_inventory():
    # Record only selected test modules and their explicit local imports.
    # New experiments outside tests_v2 are not included as executed modules.
    pending = list((ROOT/'tests_v2').glob('*.py'))
    found = {}
    while pending:
        path = pending.pop()
        key = path.relative_to(ROOT).as_posix()
        if key in found:
            continue
        found[key] = sha(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            modules = []
            if isinstance(node,ast.Import):
                modules = [item.name for item in node.names]
            elif isinstance(node,ast.ImportFrom) and node.module:
                modules = [node.module]
                if node.module == 'tools':
                    modules += ['tools.'+item.name for item in node.names]
            for module in modules:
                if module.startswith('tools.'):
                    imported = ROOT/Path(*module.split('.')).with_suffix('.py')
                    if imported.is_file():
                        pending.append(imported)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-evidence',type=Path,required=True)
    parser.add_argument('--log',type=Path,required=True)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    from ark_sim.adapters.api import implementation_digest
    run = json.loads(args.run_evidence.read_bytes())
    assert run['passed'] is True and run['exit_code'] == 0
    assert run['selection'] == ['tests_v2','-q']
    assert Path(run['runtime_module']).resolve() == ROOT/'ark_sim/__init__.py'
    assert run['implementation_before'] == run['implementation_after'] == implementation_digest()
    text = args.log.read_text(encoding='utf8')
    lines = re.findall(r'^\d+ passed in [0-9.]+s(?: \([0-9:]+\))?$',text,re.M)
    assert len(lines) == 1, 'Expected a completed all-passing suite summary'
    value = {'schema':'ark-sim/test-execution-evidence/v1','passed':True,'exit_code':0,
        'summary':lines[0],'log':args.log.resolve().relative_to(ROOT).as_posix(),'log_sha256':sha(args.log),
        'command':['tools/run_candidate_pytest.py','--runtime-root','.',*run['selection']],
        'implementation_digest_at_completion':implementation_digest(),
        'actual_runtime_module':run['runtime_module'],'run_evidence_sha256':sha(args.run_evidence),
        'test_sources_at_completion':source_inventory(),
        'input_package':args.package.resolve().relative_to(ROOT).as_posix(),'input_package_sha256':sha(args.package),
        'source_inventory_scope':'Selected tests_v2 modules plus static tools imports, recorded after successful exit; no source-start claim',
        'new_experiments_not_counted':True,'formal_approval':False}
    args.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'summary':value['summary'],'source_files':len(value['test_sources_at_completion'])}))


if __name__ == '__main__':
    main()
