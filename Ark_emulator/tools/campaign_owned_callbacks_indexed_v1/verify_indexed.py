"""Nine independent indexed lookup/death disk gates, preserve all event values."""
import copy,hashlib,json,os,random,sys,traceback,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_owned_callbacks_indexed_v1_candidate';LOCK=ROOT/'validation/campaign/campaign_owned_callbacks_indexed_v1/candidate.v1.json'
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.chapter10_bloodline_v1.build import providers,entity_id
from tools.campaign_death_event_lookup_v1.fixture import package
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_owned_callbacks_indexed_v1';N=0;ROWS=[];FACTS={};PROOFS=[];SEED=12773117
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def create(label,policy='dead'):
    global N;N+=1;p=package(policy);reg=providers()
    return Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=SEED,event_journal_path=LOG/(str(N)+'_'+label+'.active.jsonl'))
def events(s,kind):return [thaw(e) for e in s.session.events if e['type']==kind]
def stores(s):return {'world':thaw(s.session.world.snapshot()),'jobs':thaw(s.session.scheduler.snapshot()),'events':thaw(s.session._events.snapshot()),'RNG':thaw(s.session.random.snapshot()),'cache':{'causal':thaw(s.ctx.attributes.checkpoint_cache()),'last_calc':s.ctx.last_calculation_event_id,'time':s.ctx.attributes._cache_time}}
class IndexedOnly:
    def __init__(self,backing):self.backing=backing;self.reads=[]
    def __len__(self):return len(self.backing)
    def __iter__(self):raise AssertionError('Lookup materialized/iterated whole journal')
    def __getitem__(self,key):
        if type(key)is not int:raise AssertionError('Lookup requested slice/full materialization')
        self.reads.append(key);return self.backing[key]
    def __getattr__(self,name):return getattr(self.backing,name)
    def __delitem__(self,key):return self.backing.__delitem__(key)
def cpp(s,cut,end,label):
    s.advance(cut-s.session.time);cp=write_checkpoint(s,LOG/(str(N)+'_'+label+'.checkpoint.json'));r=Engine.restore(s.program,load_checkpoint(cp),providers=providers())
    assert thaw(s.checkpoint())==thaw(r.checkpoint());s.advance(end-s.session.time);r.advance(end-r.session.time)
    h=replay(s.program,s.export_replay(),providers=providers(),event_journal_path=LOG/(str(N)+'_'+label+'.head.active.jsonl'))
    obs=[observations(v,LOG/(str(N)+'_'+label+'_'+key+'.events.jsonl')) for v,key in [(s,'forward'),(r,'CP'),(h,'head')]]
    keys=('snapshot','events','event_count','continuation_state');eq=lambda v:all(v[k]==obs[0][k] for k in keys);c=[thaw(v.checkpoint()) for v in (s,r,h)]
    proof={'label':label,'cut':cut,'end':end,'checkpoint_sha256':cp['sha256'],'event_reference':cp['event_reference'],
      'observations':[{k:v[k] for k in keys} for v in obs],'disk_CP_equal':eq(obs[1]),'head_equal':eq(obs[2]),'full_checkpoint_equal':c[0]==c[1]==c[2],'full_digests':[digest(v) for v in c]}
    PROOFS.append(proof);assert proof['disk_CP_equal'] and proof['head_equal'] and proof['full_checkpoint_equal'],json.dumps(proof)
    return s
def identity():
    m=json.loads(LOCK.read_bytes());assert implementation_digest()==m['core'];assert all(sha(CAND/k)==h for k,h in m['inventory'].items())
    predecessors=m['predecessors'];assert all(all(sha(Path(p['candidate'])/k)==h for k,h in p['inventory'].items()) for p in predecessors.values())
    cb=predecessors['callback']['inventory'];ix=predecessors['indexed']['inventory'];changed=[k for k,h in m['inventory'].items() if cb.get(k)!=h];assert changed==['ark_sim/domains/death_spawns.py']
    assert m['inventory']['ark_sim/domains/death_spawns.py']==ix['ark_sim/domains/death_spawns.py'];assert m['composition']['overlap']==[]
    FACTS['identity']={'actual_core':implementation_digest(),'predecessors':{k:p['core'] for k,p in predecessors.items()},'changed_vs_callback':changed,'all_other_callback_bytes_equal':True,'all_frozen_predecessors_unchanged':True}

def exact_disk():
    s=create('exact');s.advance(70)
    for i in range(701):s.session.emit('lookup.actual.disk_probe',{'ordinal':i,'nested':{'bool':False,'null':None,'value':-0.0}},cause=None)
    chosen=[1,len(s.session._events._records),*([e['id'] for e in events(s,'entity.died')]),*([e['id'] for e in events(s,'descendant.issued')]),*([e['id'] for e in events(s,'descendant.born')])]
    reference={ref:next(thaw(e) for e in s.session.events if e['id']==ref) for ref in chosen}
    before=stores(s);raw=sha(s.session._events._records.path);records=s.session._events._records;spy=IndexedOnly(records);s.session._events._records=spy
    try:
        for ref in chosen:assert thaw(s.ctx.death_spawns.event(ref))==reference[ref]
        assert spy.reads==[ref-1 for ref in chosen]
    finally:s.session._events._records=records
    assert stores(s)==before and sha(records.path)==raw
    FACTS['exact_disk']={'actual_file':str(records.path),'record_count':len(records),'queried_IDs':chosen,'only_index_reads':[ref-1 for ref in chosen],
      'all_original_full_records_equal':True,'raw_sha256_unchanged':raw,'five_stores_equal':True,'cause_context_payload_unfiltered':True}
def negatives():
    s=create('negative');before=stores(s);n=len(s.session._events._records);rejected=[]
    for ref in (True,False,1.0,0.0,-1,0,n+1,'1',None):
        try:s.ctx.death_spawns.event(ref)
        except ValueError:rejected.append({'input':repr(ref),'type':type(ref).__name__})
        else:raise AssertionError('Invalid event ID accepted: '+repr(ref))
    assert stores(s)==before;FACTS['invalid_IDs']=rejected
def malformed():
    s=create('malformed');records=s.session._events._records;before=stores(s);cases=[]
    for change in ({'id':True},{'id':999},{'type':None},{'type':''}):
        class Bad(IndexedOnly):
            def __getitem__(self,index):return {**thaw(self.backing[index]),**change}
        s.session._events._records=Bad(records)
        try:s.ctx.death_spawns.event(1)
        except ValueError:cases.append(change)
        else:raise AssertionError('Malformed actual record accepted')
        finally:s.session._events._records=records
    assert stores(s)==before;FACTS['malformed_records']=cases
def true_issue_dispatch_no_iter():
    s=create('no_iter');back=s.session._events._records;spy=IndexedOnly(back);s.session._events._records=spy
    try:s.session.advance(70)
    finally:s.session._events._records=back
    assert len(events(s,'descendant.born'))==1 and events(s,'descendant.born')[0]['time']==41
    FACTS['actual_issue_dispatch_no_whole_iteration']={'lookup_read_count':len(spy.reads),'actual_birth_tick':41,'whole_iteration_would_raise':True}
def native_pending_cpp():
    s=cpp(create('pending'),23,70,'pending');born=events(s,'descendant.born');assert len(born)==1 and born[0]['time']==41
    child=s.ctx.entity(born[0]['payload']['child']);p=s.ctx.definition('parent')['components']['lifecycle']['death_spawns']['actions'][0]
    assert child['definition_id']==p['definition'] and child['components']['spatial']['movement']['wait_until']==180
    assert child['components']['spatial']['route']['endPosition']=={'row':2,'col':10}
    members=s.ctx.state()['timeline']['members'];assert members[str(child['id'])]['wave']==members[str(s.session.world.resolve('keeper'))]['wave']==0
    assert s.ctx.active('keeper') and s.ctx.state()['pending_waves']==0 and not s.ctx.state()['finished']
    stream=p['placement']['stream'];samples=[v for v in thaw(s.session.random.snapshot())['samples'] if v['stream']==stream]
    seed=int.from_bytes(hashlib.sha256(json.dumps([SEED,stream],ensure_ascii=False,separators=(',',':')).encode()).digest(),'big');rng=random.Random(seed);numbers=[rng.random(),rng.random()]
    assert [v['value'] for v in samples]==numbers;pos=born[0]['payload']['position'];bounds=p['placement']['random_range']
    assert pos['row']==2+(2*numbers[0]-1)*bounds['row'] and pos['col']==1+(2*numbers[1]-1)*bounds['col']
    FACTS['native_death']={'dead_tick':11,'born_tick':41,'child':child['definition_id'],'wait_until':180,'RNG':samples,'position':pos,'same_wave_keeper':True}
def native_born_cpp():
    s=cpp(create('born'),43,75,'born');assert len(events(s,'descendant.born'))==1 and s.ctx.state()['kills']==1
def withdrawal_cpp():
    s=cpp(create('withdraw','withdrawn'),12,70,'withdrawn');assert not events(s,'descendant.born') and not events(s,'descendant.issued') and s.ctx.state()['pending_waves']==0
def fault_five_stores():
    s=create('fault');capture={};orig=s.ctx.death_spawns.handle;original_emit=s.ctx.emit
    class Injected(RuntimeError):pass
    def emit(kind,payload,cause=None):
        if kind=='descendant.born':capture['inside']=stores(s);capture['actual_task']=thaw(s.session.current_task);raise Injected('Actual owned child birth fault')
        return original_emit(kind,payload,cause)
    def handle(session,payload):
        capture['before']=stores(s)
        try:return orig(session,payload)
        except Injected:capture['after']=stores(s);raise
    s.ctx.emit=emit;s.session._handlers['domain.death_spawn']=handle
    try:s.session.advance(70)
    except (Injected,RuntimeError) as error:
        assert capture.get('actual_task',{}).get('kind')=='domain.death_spawn'
        assert capture['before']==capture['after'],'Actual birth transaction failed five-store rollback'
        changed=[k for k in capture['before'] if capture['before'][k]!=capture['inside'][k]];assert set(changed)==set(capture['before']),changed
        FACTS['actual_birth_fault']={'actual_task':capture['actual_task'],'changed_inside':changed,'five_stores_equal':True,'before':{k:digest(v) for k,v in capture['before'].items()},'after':{k:digest(v) for k,v in capture['after'].items()},'error':str(error)}
    else:raise AssertionError('Actual birth fault never executed')
def main():
    m=json.loads(LOCK.read_bytes());guards={str(CAND/k):h for k,h in m['inventory'].items()};assert all(sha(p)==h for p,h in guards.items())
    for name,fn in [('one_frozen_parent_source_delta',identity),('actual_disk_full_record_equal_index_only_raw_stores_unchanged',exact_disk),
      ('strict_missing_bool_float_other_ID_rejection',negatives),('actual_malformed_record_ID_type_rejection',malformed),
      ('actual_issue_dispatch_no_whole_journal_iteration',true_issue_dispatch_no_iter),('native_parent_dead_child_route_RNG_pending_full_CPP',native_pending_cpp),
      ('native_already_born_full_CPP',native_born_cpp),('withdrawal_no_death_issuance_full_CPP',withdrawal_cpp),('actual_birth_fault_five_store_rollback',fault_five_stores)]:
        try:fn();ROWS.append({'case':name,'passed':True})
        except Exception as error:ROWS.append({'case':name,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
        finally:print(json.dumps(ROWS[-1]),flush=True);gc.collect()
    result={'schema':'ark-sim/death-event-indexed-actual-gates/v1','core':implementation_digest(),'parent_core':m['parent_core'],'candidate':str(CAND),
      'passed':all(r['passed'] for r in ROWS),'cases':ROWS,'facts':FACTS,'actual_CP_head_proofs':PROOFS,'source_guards':guards,'source_unchanged':all(sha(p)==h for p,h in guards.items()),
      'primary_modified':False,'live_source_modified':False,'prior_phase_peer_not_substituted':True,'whole_stage_claim':False,'peer_sha256':sha(__file__)}
    (OUT/'indexed.actual.v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return 0 if result['passed'] and result['source_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
