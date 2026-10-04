"""Deletion boundary, source preservation, active-run protection and drift guards."""
import json
import os
import time
from pathlib import Path

from tools.cleanup_simulation_logs import classify, execute, plan, within


def old(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.utime(path, (time.time()-7200, time.time()-7200))
    return path


def test_sources_and_compact_receipts_survive_but_raw_logs_are_deleted(tmp_path):
    log = old(tmp_path/'run.events.jsonl', b'{"id":1}\n')
    source = old(tmp_path/'input.json', json.dumps({'schemaVersion':2,'definitions':[]}).encode())
    receipt = old(tmp_path/'full.checkpoint_result.json', b'{"passed":true}')
    assert classify(log,[tmp_path]) == 'event_or_terminal_log'
    assert classify(source,[tmp_path]) is None and classify(receipt,[tmp_path]) is None
    candidates, _ = plan({'protected_paths':[]},[tmp_path],[],15)
    deleted, errors = execute(candidates,[tmp_path])
    assert len(deleted)==1 and not errors and not log.exists()
    assert source.exists() and receipt.exists()


def test_live_output_family_protected_including_sealed_continuation(tmp_path):
    live = tmp_path/'live'; other=tmp_path/'done'
    old(live/'full.active.jsonl',b'live');old(live/'full.continued.events.jsonl',b'continued')
    old(other/'full.events.jsonl',b'done')
    candidates, retained=plan({'protected_paths':[]},[tmp_path],[{'CommandLine':'python runner --output "'+str(live/'full.json')+'"'}],15)
    assert len(candidates)==1 and len(retained)==2


def test_changed_file_and_path_outside_root_cannot_be_deleted(tmp_path):
    allowed=tmp_path/'allowed';path=old(allowed/'events.jsonl',b'old')
    candidates,_=plan({'protected_paths':[]},[allowed],[],15)
    path.write_bytes(b'new value')
    deleted,errors=execute(candidates,[allowed]);assert not deleted and errors and path.exists()
    assert not within(tmp_path/'outside.jsonl',[allowed])


def test_recent_files_and_explicit_pending_verification_are_retained(tmp_path):
    pending=tmp_path/'pending';old(pending/'events.jsonl',b'pending')
    (tmp_path/'recent.log').write_text('recent')
    candidates,retained=plan({'protected_paths':[str(pending)]},[tmp_path],[],15)
    assert not candidates and len(retained)==2


def test_large_source_with_arbitrary_first_key_is_not_a_log(tmp_path):
    source=old(tmp_path/'packages/campaign/source/native.reference.json',
               json.dumps({'reader_identity':{'world':'source'},'padding':'x'*(2*1024*1024)}).encode())
    assert classify(source,[tmp_path]) is None
