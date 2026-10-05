"""V2 cleanup safety in isolated temporary fixed-root fixtures only."""
import json,os,sys,time,subprocess,uuid
from pathlib import Path
import pytest
from tools import cleanup_simulation_logs_v2 as c
from tools import run_with_log_cleanup as w
from tools import run_campaign_disk_runthrough_v20 as v

def file(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data if isinstance(data,bytes) else json.dumps(data).encode());os.utime(path,(time.time()-7200,)*2);return path
def old_log(path):return file(path,b'completed\n')
def test_source_guard_before_names_and_sizes(tmp_path):
    for name in ('input.json','commands.json','source.events.json','events.source.json','report.checkpoint.json'):
        x=file(tmp_path/name,{'reader_identity':'source','schemaVersion':2,'definitions':[],'padding':'x'*1100000});assert c.classify(x,[tmp_path]) is None
    x=file(tmp_path/'packages/campaign/source/native.reference.json',{'reader_identity':{'world':'source'},'padding':'x'*1100000});assert c.classify(x,[tmp_path]) is None
def test_small_raw_schema_beats_report_and_package_guards(tmp_path):
    for name in ('validation/m27/report.checkpoint.json','packages/chapter05_reports/ordinary_actual/enemy.dead.checkpoint.json','verification.replay.json'):
        x=file(tmp_path/name,{'schema':'ark-sim/replay/v2' if 'replay' in name else 'ark-sim/session-checkpoint/v2','kernel':{}});assert c.classify(x,[tmp_path]) is not None
    x=file(tmp_path/'result.json',{'time':0,'seconds':0,'scenario':'s','program_fingerprint':'p','runtime_fingerprint':'r','entities':[],'state':{},'events':[]});assert c.classify(x,[tmp_path])=='runtime_snapshot'
    x=file(tmp_path/'verification.report.json',{'passed':True,'implementation':'x'});assert c.classify(x,[tmp_path]) is None

def test_status_only_capture_named_receipts_are_kept(tmp_path):
    for name,value in [('capture.focused.v1.json',{'core_before':'p','core_after':'p','actual_exit':0,'result':{'passed':True}}),
                       ('capture_original.json',{'core':'p','actual_full_CPP_head_equal':True,'CPs':[{'sha256':'hash'}]}),
                       ('cleanup.capture.final.json',{'apply':True,'eligible_files':2,'reclaimed_bytes':512})]:
        path=file(tmp_path/name,value)
        assert c.classify(path,[tmp_path]) is None
    raw=file(tmp_path/'capture.core.checkpoint.json',{'core':'p','schema':'ark-sim/session-checkpoint/v2','kernel':{}})
    assert c.classify(raw,[tmp_path])=='checkpoint_or_event_capture'
def test_process_flags_spaces_equals_and_prior(tmp_path):
    paths=[tmp_path/'run one',tmp_path/'tests',tmp_path/'prior'];[old_log(p/'events.jsonl') for p in paths]
    command=f'python test --run-dir="{paths[0]}" --basetemp {paths[1]} --prior \'{paths[2]/"report.json"}\''
    candidates,retained=c.plan({'protected_paths':[]},[tmp_path],[{'CommandLine':command}],0);assert not candidates and len(retained)==3
def test_second_process_scan_blocks_new_live_run(tmp_path):
    p=old_log(tmp_path/'events.jsonl');cand,_=c.plan({},[tmp_path],[],0);deleted,errors=c.execute(cand,[tmp_path],{},[],row_supplier=lambda:[{'CommandLine':f'python runner --run-dir "{tmp_path}"'}]);assert not deleted and errors and p.exists()
def test_source_and_logs_actual_deletion(tmp_path):
    source=file(tmp_path/'events.json',{'schemaVersion':2,'scenarioDraft':{}});log=old_log(tmp_path/'events.jsonl');cand,_=c.plan({},[tmp_path],[],0);deleted,errors=c.execute(cand,[tmp_path],{},[]);assert len(deleted)==1 and not errors and source.exists() and not log.exists()
def test_copied_validation_roots_exclude_native_extraction(tmp_path):
    root=tmp_path/'unpack_work';capture=old_log(root/'candidate/ark_sim/validation/run.log')
    history=old_log(root/'candidate_history/identity/ark_sim/validation/run.log')
    native=old_log(root/'native_extract/reference.log')
    source=file(root/'candidate/ark_sim/rules/source.json',{'schemaVersion':2})
    roots=c.legacy_roots({'legacy_roots':[],'legacy_copied_validation_root':str(root)})
    assert set(roots)=={capture.parent.resolve(),history.parent.resolve()}
    candidates,_=c.plan({},roots,[],0);deleted,errors=c.execute(candidates,roots,{},[])
    assert len(deleted)==2 and not errors and not capture.exists() and not history.exists()
    assert native.exists() and source.exists()

def test_canonical_allowed_roots_preserve_sibling_boundary(tmp_path):
    allowed=tmp_path/'run';inside=old_log(allowed/'nested/events.jsonl')
    outside=old_log(tmp_path/'run_extra/events.jsonl')
    roots=c.ResolvedRoots([allowed])
    assert c.within(inside,roots) and not c.within(outside,roots)
    candidates,_=c.plan({},roots,[],0);deleted,errors=c.execute(candidates,roots,{},[])
    assert len(deleted)==1 and not errors and not inside.exists() and outside.exists()


def test_temporary_copies_only_inside_fixed_run_subtrees(tmp_path, monkeypatch):
    fixed = tmp_path / 'fixed'
    monkeypatch.setattr(c, 'FIXED_LOG_ROOT', fixed.resolve())
    copied = file(fixed / 'runs/completed/temp/test_case/input.json',
                  {'schemaVersion': 2, 'definitions': []})
    copied_code = file(fixed / 'runs/completed/pytest-of-user/pytest-0/test_case/copy.py',
                       b'# disposable test copy\n')
    original = file(tmp_path / 'workspace/tests/input.json',
                    {'schemaVersion': 2, 'definitions': []})
    authored = file(fixed / 'runs/completed/input.json',
                    {'schemaVersion': 2, 'definitions': []})
    assert c.classify(copied, [tmp_path]) == 'temporary_run_artifact'
    assert c.classify(copied_code, [tmp_path]) == 'temporary_run_artifact'
    assert c.classify(original, [tmp_path]) is None
    assert c.classify(authored, [tmp_path]) is None
    candidates, _ = c.plan({}, [tmp_path], [], 0)
    deleted, errors = c.execute(candidates, [tmp_path], {}, [])
    assert len(deleted) == 2 and not errors
    assert original.exists() and authored.exists()


def test_live_lease_still_protects_temporary_test_copies(tmp_path, monkeypatch):
    fixed = tmp_path / 'fixed'
    monkeypatch.setattr(c, 'FIXED_LOG_ROOT', fixed.resolve())
    run = fixed / 'runs/live'
    copied = file(run / 'temp/test_case/input.json', {'schemaVersion': 2})
    lease = run / 'run.lease.json'
    lease.write_text(json.dumps({'worker_pid': os.getpid(),
                                'worker_stamp': c.pid_stamp(os.getpid()),
                                'completed': False}))
    candidates, retained = c.plan({}, [run], [], 0)
    assert not candidates and len(retained) == 1 and copied.exists()
    lease.write_text('{"completed":true}')
    candidates, _ = c.plan({}, [run], [], 0)
    deleted, errors = c.execute(candidates, [run], {}, [])
    assert len(deleted) == 1 and not errors and not copied.exists()

def test_changed_file_and_outside_rejected(tmp_path):
    x=old_log(tmp_path/'events.jsonl');cand,_=c.plan({},[tmp_path],[],0);x.write_text('changed');deleted,errors=c.execute(cand,[tmp_path],{},[]);assert not deleted and errors
    cand[0]['path']=str(tmp_path.parent/'outside.log');deleted,errors=c.execute(cand,[tmp_path],{},[]);assert not deleted and errors
def test_internal_link_target_never_deleted(tmp_path):
    x=old_log(tmp_path/'target.log');link=tmp_path/'alias.log'
    try:link.symlink_to(x)
    except OSError:pytest.skip('Windows symlink creation unavailable')
    assert c.classify(link,[tmp_path]) is None
    st=x.stat();deleted,errors=c.execute([{'path':str(link),'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'kind':'event_or_terminal_log'}],[tmp_path],{},[]);assert not deleted and errors and x.exists()
def test_active_lease_protects_and_completion_releases(tmp_path):
    old_log(tmp_path/'events.jsonl');lease=tmp_path/'run.lease.json';lease.write_text(json.dumps({'worker_pid':os.getpid(),'worker_stamp':c.pid_stamp(os.getpid()),'completed':False}));cand,retained=c.plan({},[tmp_path],[],0);assert not cand and len(retained)==1
    lease.write_text('{"completed":true}');cand,retained=c.plan({},[tmp_path],[],0);assert len(cand)==1 and not retained

def test_invalid_unfinished_lease_and_actual_descendant_remain_protected(tmp_path,monkeypatch):
    old_log(tmp_path/'events.jsonl');lease=tmp_path/'run.lease.json'
    monkeypatch.setattr(c,'pid_stamp',lambda pid:555 if pid==11 else None)
    for record in ({'completed':False},{'completed':False,'worker_stamp':None},
                   {'completed':False,'workers':[{'pid':10,'stamp':444},{'pid':11,'stamp':555}]}):
        lease.write_text(json.dumps(record));cand,retained=c.plan({},[tmp_path],[],0)
        assert not cand and len(retained)==1
    lease.write_text(json.dumps({'completed':False,'workers':[{'pid':10,'stamp':444}]}))
    cand,retained=c.plan({},[tmp_path],[],0);assert len(cand)==1 and not retained

def test_interrupted_launcher_keeps_live_descendant_lease(tmp_path,monkeypatch):
    alive={10:444,11:555,12:666};monkeypatch.setattr(w,'pid_stamp',lambda pid:alive.get(pid))
    monkeypatch.setattr(w,'processes',lambda:[{'ProcessId':11,'ParentProcessId':10},{'ProcessId':12,'ParentProcessId':99}])
    class Launcher:
        pid=10
        def poll(self):return None if 10 in alive else 1
        def terminate(self):alive.pop(10)
        def wait(self):return 1
    assert w.stop_owned_processes(tmp_path,Launcher())==[{'pid':11,'stamp':555}]
    assert w.live_lease(tmp_path)
    record=json.loads((tmp_path/'run.lease.json').read_bytes())
    assert {worker['pid'] for worker in record['workers']}=={10,11}
    alive.pop(11);assert not w.live_lease(tmp_path)

def test_finished_process_is_not_live_while_parent_still_holds_handle():
    process=subprocess.Popen([sys.executable,'-c','pass'])
    assert process.wait()==0
    assert c.pid_stamp(process.pid) is None
def test_receipt_extraction_is_bounded(tmp_path,monkeypatch):
    x=file(tmp_path/'report.json',{'schema':'report','passed':True,'events':[],'padding':'x'*2000000});cand,_=c.plan({},[tmp_path],[],0)
    original=Path.read_bytes
    def read(p):
        if p==x:raise AssertionError('Full report materialized')
        return original(p)
    monkeypatch.setattr(Path,'read_bytes',read);c.compact_receipts(cand,tmp_path/'receipts');assert len(list((tmp_path/'receipts').glob('*.json')))==1
def test_main_errors_nonzero_and_result_is_truthful(tmp_path,monkeypatch):
    old_log(tmp_path/'events.jsonl');policy=tmp_path/'policy.input.json';policy.write_text(json.dumps({'log_root':str(c.FIXED_LOG_ROOT),'protected_paths':[],'minimum_age_minutes':0}))
    monkeypatch.setattr(c,'POLICY',policy);monkeypatch.setattr(c,'processes',lambda:[]);monkeypatch.setattr(c,'execute',lambda *a,**k:([],[{'path':'blocked','reason':'denied'}]))
    output=c.FIXED_LOG_ROOT/'cleanup'/('peer_result_'+uuid.uuid4().hex+'.json');monkeypatch.setattr(sys,'argv',['cleanup','--run-dir',str(tmp_path),'--apply','--result-json',str(output)]);assert c.main()==2;result=json.loads(output.read_bytes());assert not result['fully_cleaned'] and result['error_count']==1 and result['remaining_files']==1
def test_result_json_outside_or_existing_and_bad_root_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'processes',lambda:[])
    for output in (tmp_path/'input.json',c.FIXED_LOG_ROOT/'receipts'/'existing_input.json'):
        if output.name=='existing_input.json':output.parent.mkdir(parents=True,exist_ok=True);output.write_text('{"schemaVersion":2}')
        monkeypatch.setattr(sys,'argv',['cleanup','--run-dir',str(tmp_path),'--result-json',str(output)])
        with pytest.raises(ValueError):c.main()
        if output.name=='existing_input.json':output.unlink()
    policy=tmp_path/'policy.input.json';policy.write_text('{"log_root":"D:/unsafe"}');monkeypatch.setattr(c,'POLICY',policy);monkeypatch.setattr(sys,'argv',['cleanup','--run-dir',str(tmp_path)])
    with pytest.raises(ValueError):c.main()
def test_run_new_fixed_directory_only(tmp_path):
    with pytest.raises((ValueError,FileExistsError)):w.new_run(tmp_path)
    with pytest.raises(ValueError):w.new_run(Path('D:/outside_cleanup_test'))
def test_launcher_ancestors_only_same_argv_ignored(monkeypatch):
    rows=[{'ProcessId':1,'ParentProcessId':2,'CommandLine':'"D:/python/python.exe" cleanup --run-dir E:/owned'},
          {'ProcessId':2,'ParentProcessId':3,'CommandLine':'"D:/venv/python.exe" cleanup --run-dir E:/owned'},
          {'ProcessId':3,'ParentProcessId':0,'CommandLine':'python different --run-dir E:/other'},
          {'ProcessId':4,'ParentProcessId':0,'CommandLine':'python cleanup --run-dir E:/owned'}]
    monkeypatch.setattr(c,'processes',lambda:rows);assert {r['ProcessId'] for r in c.active_processes({1})}=={3,4}
def test_v20_failure_and_receipt_copy_error_still_clean(tmp_path,monkeypatch):
    calls=[]
    class Worker:
        pid=999999
        def __init__(self,command,**kw):
            out=Path(command[command.index('--output')+1]);file(out.with_suffix('.events.jsonl'),b'raw');file(out,{'passed':False})
        def wait(self):return 9
        def poll(self):return 9
    monkeypatch.setattr(v.subprocess,'Popen',Worker);monkeypatch.setattr(v,'start_lease',lambda *a:None)
    def finish(run,code,metadata,process):calls.append((run,code,metadata));cand,_=c.plan({},[run],[],0);deleted,errors=c.execute(cand,[run],{},[]);assert deleted and not errors;return code
    monkeypatch.setattr(v,'finish',finish);monkeypatch.setattr(v,'compact_worker',lambda *a:(_ for _ in ()).throw(OSError('receipt copy failed')))
    monkeypatch.setattr(sys,'argv',['v20','--output',str(tmp_path/'kept.json')]);assert v.main()==9;assert calls[0][2]['worker_error'] and not list(calls[0][0].glob('*.jsonl'))
