"""Current canonical content input; historical helpers remain byte-preserved."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('CAMPAIGN_SUMMON_PACKAGE',str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json'))
