"""Actual full 0-1 disk journal gate, with native process memory observation."""
import ctypes,gc,hashlib,importlib.util,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m82_disk_environment_candidate'
CORE='65134744f50a9a1641f339965a8f4925927e5de51aedff9a39eea0550e887522'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay


def memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(k,ctypes.c_size_t) for k in
            ('peak_working_set','working_set','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=ctypes.c_void_p
    api=ctypes.WinDLL('psapi');api.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
    if not api.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):raise ctypes.WinError()
    return {'working_set':counters.working_set,'peak_working_set':counters.peak_working_set,'private':counters.private}


def comp(v):return {k:v[k] for k in ('snapshot','events','event_count','continuation_state')}


def main():
    import ark_sim
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    out=ROOT/'validation/campaign/m82_disk_environment/actual_0_1_disk';out.mkdir(parents=True,exist_ok=True)
    report_path=out/'final.json'
    if report_path.exists() or (out/'active.jsonl').exists():raise FileExistsError('Preserve baseline evidence')
    helper_path=ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py';spec=importlib.util.spec_from_file_location('disk_baseline_helper',helper_path)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    package=ROOT/'packages/ark_content/level_main_00_01.json';commands=ROOT/'scenarios/level_main_00_01/commands.json'
    files=[Path(__file__),package,commands,helper_path,Path(helper._v13.__file__),Path(helper._v13._v12.__file__),ROOT/'tools/campaign_ordered_checkpoint.py',
        *list((RUNTIME/'ark_sim').rglob('*.py')),*list((RUNTIME/'ark_sim').rglob('*.json'))]
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();started=time.monotonic();measure=[{'phase':'before','time':0,**memory()}]
    program=Compiler().compile(package);s=Engine.create(program,seed=123,event_journal_path=out/'active.jsonl')
    for command in json.loads(commands.read_bytes()):
        action=dict(command);tick=action.pop('at');s.submit(action,at=tick)
    s.session.advance(300);cp=helper.write_checkpoint(s,out/'checkpoint.json')
    while not s.ctx.state()['finished'] and s.session.time<3000:
        s.session.advance(150);measure.append({'phase':'original','time':s.session.time,**memory()})
        print(json.dumps({'phase':'original','tick':s.session.time,'events':len(s.session._events._records),'memory':measure[-1]}),flush=True)
    assert s.ctx.state()['finished'] and s.ctx.state()['kills']==11 and s.ctx.state()['leaks']==0
    end=s.session.time;original=helper.observations(s,out/'original.events.jsonl');record=s.export_replay()
    del s;gc.collect();measure.append({'phase':'original_released','time':end,**memory()})
    r=Engine.restore(program,helper.load_checkpoint(cp));r.session.advance(end-r.session.time);continued=helper.observations(r,out/'continued.events.jsonl')
    assert comp(original)==comp(continued);del r;gc.collect();measure.append({'phase':'continuation_released','time':end,**memory()})
    repeated=replay(program,record,event_journal_path=out/'replay.active.jsonl');replayed=helper.observations(repeated,out/'replayed.events.jsonl')
    assert comp(original)==comp(replayed);measure.append({'phase':'replay_completed','time':end,**memory()});del repeated;gc.collect()
    after=guard();assert before==after and implementation_digest()==CORE
    report={'passed':True,'core_start':CORE,'core_end':implementation_digest(),'source_start':before,'source_end':after,
        'input_package':str(package),'commands':str(commands),'checkpoint':cp,'original':original,'continued':continued,'replayed':replayed,
        'observed_end':end,'native_memory_measurements':measure,'seconds':time.monotonic()-started,
        'scope':'Actual0-1 complete fullvalues/disk-referenceCP/replay and Windows working-set observations; 181937event-scale, no million-event or 36stage proof',
        'base_life_override':False,'whole_campaign_stage_accepted':False,'actual_client_verified':False}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':True,'events':original['event_count'],'bytes':original['export']['bytes'],'peak_working_set':measure[-1]['peak_working_set'],'seconds':report['seconds']}),flush=True)


if __name__=='__main__':main()
