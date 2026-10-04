import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]


def test_completed_original_recovery_saves_terminal_phase_and_reuses_actual_bytes(tmp_path):
    from tools.experiments.disk_runthrough_m81.test_cli import test_actual_disk_cli_complete_reference_cp_replay_never_materializes_history,RUNTIME,HELPER
    test_actual_disk_cli_complete_reference_cp_replay_never_materializes_history(tmp_path)
    output=tmp_path/'report.json'
    # Simulate a lost worker after its original result was durably produced.
    output.unlink()
    args=[sys.executable,'tools/finish_pending_disk_runthrough_v16.py','--runtime-root',str(RUNTIME),'--output',str(output),
        '--package',str(tmp_path/'input.json'),'--evidence-helper',str(HELPER)]
    first=subprocess.run(args,cwd=ROOT,capture_output=True,text=True);assert first.returncode==0,first.stdout+first.stderr
    report=json.loads(output.read_bytes());assert report['passed'] and report['checkpoint_equal'] and report['replay_equal']
    hashes={phase:json.loads(output.with_suffix('.'+phase+'.terminal.metadata.json').read_bytes())['sha256'] for phase in ('continuation','replay')}
    second=subprocess.run(args,cwd=ROOT,capture_output=True,text=True);assert second.returncode==0,second.stdout+second.stderr
    assert second.stdout.count('restored_terminal')==2
    for phase in hashes:
        assert json.loads(output.with_suffix('.'+phase+'.terminal.metadata.json').read_bytes())['sha256']==hashes[phase]
