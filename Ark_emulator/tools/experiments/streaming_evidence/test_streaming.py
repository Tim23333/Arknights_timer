"""Full payload canonical evidence matches existing digest exactly."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim.contracts import digest,freeze,thaw
from tools.campaign_streaming_evidence import canonical_hash,write_canonical,observations,export_events
from tools.experiments.m26.test_decisions import fixture,make


@pytest.mark.parametrize('value',[None,True,1,-0.0,1.1,'中文\\\n"',{'z':[],'a':[None,True,1,1.0,{'🙂':'数据'}]}])
def test_exact_existing_digest_for_mutable_and_frozen_json(value):
    assert canonical_hash(value)==digest(value)
    assert canonical_hash(freeze(value))==digest(value)


def test_actual_model_snapshot_events_and_continuation_state():
    sim=make(fixture());sim.advance(8);before=sim.checkpoint();o=observations(sim)
    assert o['snapshot']==digest(sim.snapshot())
    assert o['events']==digest(thaw(sim.session.events))
    assert o['event_count']==len(sim.session.events)
    assert sim.checkpoint()==before


def test_complete_journal_export_roundtrip_and_hash(tmp_path):
    sim=make(fixture());sim.advance(8);path=tmp_path/'events.jsonl';r=export_events(path,sim)
    assert [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]==thaw(sim.session.events)
    assert r['events']==len(sim.session.events) and r['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    target=tmp_path/'frozen.json';write_canonical(target,freeze({'events':sim.session.events}))
    assert json.loads(target.read_bytes())=={'events':thaw(sim.session.events)}


def test_nonfinite_not_silently_serialized():
    with pytest.raises(ValueError):canonical_hash({'hp':float('nan')})
