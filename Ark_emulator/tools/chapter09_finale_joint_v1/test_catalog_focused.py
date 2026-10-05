"""Fresh exact108 catalog and source-profile compilation on the new joint."""
import sys, json, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
CAND = (ROOT/'../unpack_work/campaign_c9_finale_joint_v1_candidate').resolve()
sys.path.insert(0, str(CAND)); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_mandra_full_v1.catalog108 import test_catalog_exact107_plus_capture_and_immutable
from tools.chapter09_mandra_v1.test_author import fixture
from tools.chapter09_mandra_v1.build import providers

files = [p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
files += [Path(__file__), ROOT/'tools/chapter09_mandra_full_v1/catalog108.py',
          ROOT/'tools/chapter09_mandra_full_v1/contracts.parent107.json',
          ROOT/'tools/chapter09_mandra_v1/build.py', ROOT/'tools/chapter09_mandra_v1/test_author.py']
for folder in ['mandra','receiver_hooks_v2']:
    files += list((ROOT/'packages/campaign/chapter09_consumers'/folder).glob('*.json'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before = {str(p): sha(p) for p in files}; core = implementation_digest()
test_catalog_exact107_plus_capture_and_immutable()
programs = []
for profile in ['talent_prefix','skill_prefix']:
    program = Compiler(providers=providers()).compile(fixture(profile))
    programs.append({'profile': profile, 'fingerprint': program.fingerprint,
                     'dependency_count': len(program.dependency_ids), 'metadata': program.to_dict()['metadata']})
after = {str(p): sha(p) for p in files}; assert before == after and core == implementation_digest()
report = {'core_before': core, 'core_after': implementation_digest(), 'actual_exit': 0,
          'catalog_count': 108, 'old107_exact': True, 'catalog_immutable': True, 'programs': programs,
          'source_before': before, 'source_after': after, 'source_equal': True}
path = ROOT/'validation/campaign/chapter09_finale_joint_v1/catalog.focused.v1.json'; assert not path.exists()
path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8'); print(json.dumps({'actual_exit': 0,'core':core}))
