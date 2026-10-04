"""Monitoring a long simulation must not alter calculations or execution."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m27_event_intern_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from tools.campaign_run_diagnostics import summarize
from tools.experiments.runthrough.test_profile import fixture


def test_diagnostic_alive_population_and_state_are_readonly():
    p=fixture();p['entities'][0]['components']['attributes']['base']['move_speed']=0
    s=Engine.create(Compiler().compile(p),seed=0);s.advance(1);before=s.checkpoint();d=summarize(s)
    assert d['tick']==1 and len(d['alive_enemies'])==1 and d['pending']==2
    assert d['alive_enemies'][0]['resources']['hp']==10
    assert s.checkpoint()==before
