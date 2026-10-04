import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m57_obstacle_reentry_candidate'
sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import pytest
raise SystemExit(pytest.main(['-q',str(Path(__file__).parent/'test_independent.py')]))
