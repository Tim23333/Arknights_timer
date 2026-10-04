"""Assert the joined runtime before executing copied numerical author gates."""
import argparse
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_c9_pillar_channel_joint_v1_candidate'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
import ark_sim
from ark_sim.adapters.api import implementation_digest

parser = argparse.ArgumentParser()
parser.add_argument('script', choices=['test_author.py', 'test_regression.py', 'test_context.py', 'test_restore.py'])
args = parser.parse_args()
assert Path(ark_sim.__file__).resolve().parent == RUNTIME / 'ark_sim'
assert implementation_digest() == '53ee67c10a664707d8b23bd1191bd5995085ed20cd92837bb8ab64c63f93ff7c'
sys.argv = [args.script]
runpy.run_path(str(Path(__file__).with_name(args.script)), run_name='__main__')
