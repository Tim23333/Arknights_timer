"""New runner retains whole-process, full journal, checkpoint and replay."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim.adapters.api import implementation_digest
from tools.build_campaign_runthrough_input import apply,encoded
from tools.experiments.runthrough.test_profile import fixture


def test_streaming_complete_three_leaks_and_full_journal(tmp_path):
    p=tmp_path/'fixture.json';p.write_bytes(encoded(apply(fixture(),'synthetic')))
    c=tmp_path/'commands.json';c.write_text('[]\n',encoding='utf8');out=tmp_path/'result.json'
    r=subprocess.run([sys.executable,str(ROOT/'tools/run_campaign_streaming_runthrough.py'),'--runtime-root',str(RUNTIME),
        '--expected-core',implementation_digest(),'--package',str(p),'--commands',str(c),'--output',str(out),'--max-ticks','100','--checkpoint-at','2'],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0,r.stdout+r.stderr
    report=json.loads(out.read_bytes());assert report['passed'] and report['identity_stable']
    assert report['checkpoint_equal'] is True and report['replay_equal'] is True
    assert report['state']['leaks']==3 and report['base_life_final']==99996
    assert report['journal']['events']==report['observations']['event_count']
    lines=(out.with_suffix('.events.jsonl')).read_text(encoding='utf8').splitlines()
    assert len(lines)==report['journal']['events'] and json.loads(lines[-1])['id']==len(lines)
    assert report['actual_game_accuracy_verified'] is False
