import json,hashlib,threading,copy,importlib.util,math
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import Intent,thaw
from ark_sim.tools.replay import replay
from ark_sim.kernel.events import EventLog
ROOT=Path(__file__).resolve().parents[3];HELPER=ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py';spec=importlib.util.spec_from_file_location('peer_v13',HELPER);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
INPUTS=[];CAPTURES=[]
def canonical(v):return hashlib.sha256(json.dumps(thaw(v),sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def create(tmp,disk=True):
 p={'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/counter','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':7}},'resources':{'zeta':{'initial':0,'capacity':1000,'recovery_rate':30},'alpha':{'initial':0,'capacity':1000,'recovery_rate':60}}}}],'scenarioDraft':{'id':'scene/ordered_peer','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'initialEntities':[{'definition':'unit/counter','instanceAlias':'counter','position':{'row':0,'col':0}}]}}
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'seed':710031});kwargs={'event_journal_path':tmp/'active.jsonl'} if disk else {};return Engine.create(Compiler().compile(json.loads(raw)),seed=710031,**kwargs)


def test_ordered_actual_disk_reload_and_reference_independent_branch(tmp_path):
 s=create(tmp_path);s.advance(3);meta=helper.write_checkpoint(s,tmp_path/'main.json');actual=(tmp_path/'main.json').read_bytes();assert hashlib.sha256(actual).hexdigest()==meta['sha256'];loaded=helper.load_checkpoint(meta)
 refs=loaded['kernel']['events']['reference'];sealed=Path(refs['path']).read_bytes();assert hashlib.sha256(sealed).hexdigest()==refs['sha256'] and len(sealed)==refs['bytes']
 restored=Engine.restore(s.program,loaded);assert list(restored.ctx.get('counter',('resources',)))==['zeta','alpha'];s.advance(60);restored.advance(60);rep=replay(s.program,s.export_replay(),event_journal_path=tmp_path/'replay.jsonl');assert s.snapshot()==restored.snapshot()==rep.snapshot()
 assert Path(refs['path']).read_bytes()==sealed
 CAPTURES.append({'expected':'zeta then alpha order retained, full values equal','metadata':meta,'main_bytes_sha256':hashlib.sha256(actual).hexdigest(),'snapshot':s.snapshot(),'commands':s.export_replay(),'checkpoint_equal':True,'replay_equal':True})


def test_memory_disk_complete_values_and_mutable_input_isolation(tmp_path):
 disk=create(tmp_path);memory=create(tmp_path,False);shared=[-0.0,2**60,1.0,'雪'];payload={'z':shared,'a':shared}
 for sim in (memory,disk):sim.session.emit('probe.values',payload);sim.advance(3)
 shared.append('later');assert disk.snapshot()==memory.snapshot();p=thaw(disk.session.events[-1]);assert not any('later' in str(e['payload']) for e in disk.session.events)
 record=next(e for e in disk.session.events if e['type']=='probe.values');assert type(record['payload']['z'][1]) is int and type(record['payload']['z'][2]) is float and math.copysign(1,record['payload']['z'][0])==-1
 with pytest.raises(TypeError):record['payload']['z'][0]=9


def test_nested_atomic_rollback_keeps_logical_prefix_rng_world_and_tasks(tmp_path):
 s=create(tmp_path);s.session.register_handler('probe.task',lambda session,payload:None);before=s.checkpoint();file=s.session._events._records.path
 with pytest.raises(ValueError):
  with s.session.atomic():
   s.ctx.resources.adjust('counter','zeta',value=10);s.session.random.sample('imp');s.session.schedule('probe.task',{},20);s.session.emit('probe.outer',{'x':1})
   with s.session.atomic():s.session.emit('probe.inner',{'x':2})
   raise ValueError('abort')
 assert s.checkpoint()==before;s.session.emit('probe.after',{'x':3});records=s.session.events;assert records[-1]['id']==before['kernel']['events']['next_id'] and not any(e['type']=='probe.inner' for e in records)
 exported=s.session.export_events_jsonl(tmp_path/'export.jsonl');assert exported['count']==len(records) and Path(exported['path']).read_bytes().endswith(b'\n')

class PartialWrite:
 def __init__(self,file):self.file=file;self.calls=0
 def __getattr__(self,name):return getattr(self.file,name)
 def write(self,data):
  self.calls+=1
  if self.calls==2:self.file.write(data[:7]);raise OSError('partial disk write')
  return self.file.write(data)


def test_batch_disk_failure_does_not_publish_world_scheduler_or_nextid(tmp_path):
 s=create(tmp_path);before=s.checkpoint();store=s.session._events._records;orig=store._file;store._file=PartialWrite(orig);ref=s.session.world.resolve('counter')
 try:
  with pytest.raises(OSError):s.session.commit([Intent('set',ref,('resources','zeta','current'),8),Intent('schedule',data={'kind':'probe.future','payload':{},'at':20}),Intent('emit',data={'type':'probe.one','payload':{}}),Intent('emit',data={'type':'probe.two','payload':{}})])
 finally:store._file=orig
 assert s.checkpoint()==before;s.session.emit('probe.clean',{});assert s.session.events[-1]['id']==before['kernel']['events']['next_id']


def test_actual_main_and_sealed_reference_mutations_reject(tmp_path):
 s=create(tmp_path);meta=helper.write_checkpoint(s,tmp_path/'main.json');raw=Path(meta['path']).read_bytes();Path(meta['path']).write_bytes(raw+b' ')
 with pytest.raises(ValueError):helper.load_checkpoint(meta)
 Path(meta['path']).write_bytes(raw);cp=helper.load_checkpoint(meta);cp_bad=copy.deepcopy(cp);cp_bad['kernel']['events']['reference']['sha256']='0'*64
 with pytest.raises(ValueError):Engine.restore(s.program,cp_bad)
 sealed=Path(cp['kernel']['events']['reference']['path']);old=sealed.read_bytes();sealed.write_bytes(old+b' ')
 with pytest.raises(ValueError):Engine.restore(s.program,cp)


def test_active_corruption_is_checked_after_preceding_read(tmp_path):
 s=create(tmp_path);store=s.session._events._records;first=s.session.events[0];path=store.path
 with path.open('r+b') as file:
  raw=file.readline();changed=raw.replace(b'"id":1',b'"id":9',1);assert changed!=raw;file.seek(0);file.write(changed);file.flush()
 with pytest.raises(ValueError):s.session.events


def test_exclusive_v13_publication_race_keeps_one_winner_and_cleans_staging(tmp_path,monkeypatch):
 s=create(tmp_path);path=tmp_path/'main.json';barrier=threading.Barrier(2);orig=helper._v13.os.link;success=[];errors=[]
 def link(a,b):barrier.wait(timeout=5);return orig(a,b)
 monkeypatch.setattr(helper._v13.os,'link',link)
 def worker():
  try:success.append(helper.write_checkpoint(s,path))
  except BaseException as error:errors.append(type(error).__name__)
 threads=[threading.Thread(target=worker) for _ in range(2)]
 for thread in threads:thread.start()
 for thread in threads:thread.join(10);assert not thread.is_alive()
 assert len(success)==1 and errors==['FileExistsError'] and hashlib.sha256(path.read_bytes()).hexdigest()==success[0]['sha256'] and not list(tmp_path.glob('.main.json.tmp-*'))
 with pytest.raises(FileExistsError):helper.write_checkpoint(s,path)


def test_v13_stable_observations_equal_complete_snapshot(tmp_path):
 s=create(tmp_path);s.advance(4);value=helper.observations(s,tmp_path/'obs.jsonl');assert value['snapshot']==canonical(s.snapshot()) and value['events']==canonical(s.session.events) and value['event_count']==len(s.session.events)
 assert hashlib.sha256(Path(value['export']['path']).read_bytes()).hexdigest()==value['export']['sha256']


def test_observation_advance_race_cannot_mix_different_boundaries(tmp_path):
 s=create(tmp_path);s.advance(3);before=canonical(s.snapshot());old=s.session.export_events_jsonl;worker=[]
 def export(path):
  result=old(path);thread=threading.Thread(target=lambda:s.advance(1));worker.append(thread);thread.start();thread.join(.2);return result
 s.session.export_events_jsonl=export;error=None;value=None
 try:value=helper.observations(s,tmp_path/'obs_race.jsonl')
 except (RuntimeError,ValueError) as caught:error=type(caught).__name__
 for thread in worker:thread.join(5);assert not thread.is_alive()
 after=canonical(s.snapshot());CAPTURES.append({'expected':'reject or one internally consistent complete boundary','before_snapshot_hash':before,'after_snapshot_hash':after,'observation':value,'error':error,'after_snapshot':s.snapshot()})
 assert error is not None or value['snapshot'] in [before,after]


def test_export_mutation_between_export_and_observation_is_not_accepted(tmp_path):
 s=create(tmp_path);old=s.session.export_events_jsonl
 def export(path):
  result=old(path);p=Path(path);raw=p.read_bytes();changed=raw.replace(b'"time":0',b'"time":9',1);assert changed!=raw;p.write_bytes(changed);return result
 s.session.export_events_jsonl=export
 with pytest.raises(ValueError):helper.observations(s,tmp_path/'changed_export.jsonl')


def test_reference_count_bool_is_not_an_integer_schema_count(tmp_path):
 log=EventLog();log.enable_disk(tmp_path/'one.jsonl');log.emit('one',{},0);ref=log.snapshot(event_reference=True);ref['reference']['count']=True
 with pytest.raises((TypeError,ValueError)):EventLog().restore(ref)


@pytest.mark.parametrize('key',['count','bytes'])
@pytest.mark.parametrize('bad',[True,False,-1,1.0,None,'1',{},[]])
def test_reference_numeric_metadata_strict_before_branch_creation(key,bad,tmp_path):
 log=EventLog();log.enable_disk(tmp_path/'numeric.jsonl');log.emit('one',{},0);ref=log.snapshot(event_reference=True);ref['reference'][key]=bad;before=set(tmp_path.glob('*.branch-*'))
 with pytest.raises((TypeError,ValueError)):EventLog().restore(ref)
 assert set(tmp_path.glob('*.branch-*'))==before


def test_reference_empty_prefix_count_size_zero_and_frozen_deepcopy_valid(tmp_path):
 from ark_sim.contracts import freeze
 log=EventLog();log.enable_disk(tmp_path/'empty.jsonl');ref=log.snapshot(event_reference=True);assert ref['reference']['count']==0 and ref['reference']['bytes']==0
 r=EventLog();r.restore(freeze(copy.deepcopy(ref)));assert r.records==();r.emit('new',{'x':1},0);assert r.records[0]['id']==1 and log.records==()


def test_same_thread_reentrant_mutation_observation_rejects(tmp_path):
 s=create(tmp_path);old=s.session.export_events_jsonl
 def export(path):
  result=old(path);s.ctx.resources.adjust('counter','zeta',value=8);return result
 s.session.export_events_jsonl=export
 with pytest.raises(RuntimeError,match='changed'):helper.observations(s,tmp_path/'reentrant.jsonl')


def test_mutated_export_and_rehashed_header_still_not_owned_journal(tmp_path):
 s=create(tmp_path);old=s.session.export_events_jsonl
 def export(path):
  result=old(path);p=Path(path);raw=p.read_bytes();value=json.loads(raw.splitlines()[0]);value['payload']={'forged':True};lines=raw.splitlines(keepends=True);lines[0]=(json.dumps(value,separators=(',',':'))+'\n').encode();changed=b''.join(lines);p.write_bytes(changed);return {**result,'sha256':hashlib.sha256(changed).hexdigest(),'bytes':len(changed)}
 s.session.export_events_jsonl=export
 with pytest.raises(ValueError,match='owned logical journal'):helper.observations(s,tmp_path/'rehashed.jsonl')


def test_explicit_atomic_context_observation_not_publish_uncommitted_state(tmp_path):
 s=create(tmp_path);before=s.checkpoint()
 with s.session.atomic():
  with pytest.raises(RuntimeError,match='idle'):helper.observations(s,tmp_path/'atomic.jsonl')
 assert s.checkpoint()==before and not (tmp_path/'atomic.jsonl').exists()


def test_advance_is_queued_until_export_and_complete_observation_end(tmp_path):
 s=create(tmp_path);s.advance(3);before=canonical(s.snapshot());old=s.session.export_events_jsonl;started=threading.Event();done=threading.Event();threads=[]
 def worker():started.set();s.advance(1);done.set()
 def export(path):
  result=old(path);t=threading.Thread(target=worker);threads.append(t);t.start();assert started.wait(2);assert not done.wait(.05);return result
 s.session.export_events_jsonl=export;value=helper.observations(s,tmp_path/'locked.jsonl');assert value['snapshot']==before
 for t in threads:t.join(5);assert not t.is_alive()
 assert done.is_set() and s.session.time==4
