"""Independent chapter0 native mode numerical and full-continuation probes."""
import copy,hashlib,json,math,os,sys,traceback,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
SOURCE=ROOT/'packages/campaign/chapter0_source_prepare/enemies.native.v1.json';MODULE=ROOT/'packages/campaign/chapter0_consumers/enemies.module.v1.json'
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter0_source_numeric_peer_v1';ROWS=[];PROOFS=[];N=0
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ev(s,k):return [thaw(e) for e in s.session.events if e['type']==k]
def fixture(key,speed=1,change=False,multi=False,far=False):
    p=json.loads(MODULE.read_bytes());enemy=next(e for e in p['entities'] if e['id']=='unit/ch0/'+key)
    if speed!=1:enemy['components']['attributes']['base']['attack_speed_ratio']=speed
    for label,res in [('first',17),('second',61)]:
        p['entities'].append({'id':'unit/peer0/'+label,'kind':'entity','tags':['player'], 'components':{
          'attributes':{'base':{'max_hp':11731,'atk':0,'def':83,'mres':res,'block_count':3 if multi else 1}},
          'resources':{'hp':{'role':'health','initial':11731,'capacity':11731},'sp':{'initial':7,'capacity':43}},
          'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{'blocking':True},'abilities':[],
          'deployable':{'base_cost':0,'terrain':'ground','capacity':2,'cooldown_seconds':0},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    pos={'row':1,'col':2 if far else 0};air=key=='enemy_1005_yokai'
    initial=[{'definition':enemy['id'],'instanceAlias':'enemy','position':pos,'route':{'motionMode':'FLY' if air else 'WALK','startPosition':pos,'endPosition':{'row':1,'col':8},'checkpoints':[]}},
      {'definition':'unit/peer0/first','instanceAlias':'first','position':{'row':1,'col':0}}]
    if multi:initial.append({'definition':enemy['id'],'instanceAlias':'enemy2','position':pos,'route':{'motionMode':'WALK','startPosition':pos,'endPosition':{'row':1,'col':8},'checkpoints':[]}})
    p['scenarioDraft']={'id':'scene/peer0/'+key+'/'+str(speed)+'/'+str(change)+'/'+str(multi)+'/'+str(far),'ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':9},'initialEntities':initial,
      'roster':['unit/peer0/first','unit/peer0/second'],'resources':{'dp':{'initial':100,'capacity':100}}}
    if change:p['scenarioDraft']['commands']=[{'at':40,'action':'withdraw','source':'first'},{'at':60,'action':'deploy','entity':'unit/peer0/second','alias':'second','row':1,'col':1}]
    return p
def cpp(p,label,cut=5,end=130):
    global N;N+=1;program=Compiler().compile(p);a=Engine.create(program,seed=8043,event_journal_path=LOG/(str(N)+'.active.jsonl'));a.advance(cut)
    pin=write_checkpoint(a,LOG/(str(N)+'.checkpoint.json'));b=Engine.restore(program,load_checkpoint(pin));assert thaw(a.checkpoint())==thaw(b.checkpoint())
    a.advance(end-cut);b.advance(end-cut);h=replay(program,a.export_replay(),event_journal_path=LOG/(str(N)+'.head.active.jsonl'))
    obs=[observations(s,LOG/(str(N)+'.'+key+'.events.jsonl')) for s,key in [(a,'forward'),(b,'CP'),(h,'head')]];keys=('snapshot','events','event_count','continuation_state')
    equal=all(all(v[k]==obs[0][k] for k in keys) for v in obs[1:]);c=[thaw(s.checkpoint()) for s in (a,b,h)]
    PROOFS.append({'case':label,'checkpoint_sha256':pin['sha256'],'four_observations_equal':equal,'full_checkpoint_equal':c[0]==c[1]==c[2],'digests':[digest(v) for v in c]});assert equal and c[0]==c[1]==c[2]
    return a
def oracle(v):
    attrs=v['native_enemy']['resolved']['attributes'];node=v['modes'][0]['nodes']['_combat'];binding=node.get('animation_binding')
    return {'atk':attrs['atk'],'base_interval':attrs['baseAttackTime'],'native_speed':attrs['attackSpeed']/100,'scale':node['raw'].get('_atkScale'),
      'hit_frame':next(e['frame'] for e in binding['events'] if e['name']=='OnAttack') if binding else None,'full_frame':binding['duration']['frame'] if binding else None}
def numerical(v,speed=1,far=False):
    key=v['prefab_key'];o=oracle(v);label=key+'/'+str(speed)+'/'+str(far);s=cpp(fixture(key,speed,far=far),label);hits=ev(s,'damage.accepted');starts=ev(s,'ability.started');finishes=ev(s,'ability.finished')
    details={'source_oracle':o,'hits':hits,'start_times':[e['time'] for e in starts],'finish_times':[e['time'] for e in finishes],'HP':s.ctx.resources.current('first','hp'),'SP':s.ctx.resources.current('first','sp')}
    assert details['SP']==7 and s.ctx.active('first')
    if o['hit_frame'] is None or far:
        assert not hits and not starts and details['HP']==11731
        if o['hit_frame'] is None:assert s.ctx.get('enemy',('runtime','blocked_by')) is None and s.ctx.get('enemy',('spatial','position'))['col']>0
    else:
        amount=max(o['atk']*o['scale']-83,o['atk']*o['scale']*.05);assert all(h['payload']['amount']==amount for h in hits)
        assert details['HP']==11731-len(hits)*amount and s.ctx.resources.current('enemy','hp')==v['native_enemy']['resolved']['attributes']['maxHp']
        # The declared standard policy scales the interval only. Speed-scaled
        # animation timing is an unproven source/body gap, preserved in v1.
        gap=math.ceil(o['base_interval']*30/speed-1e-10);wind=o['hit_frame'];duration=o['full_frame']
        times=[e['time'] for e in starts];assert len(times)>=2 and all(b-a==gap for a,b in zip(times,times[1:]))
        assert [e['time'] for e in hits]==[t+wind for t in times if t+wind<=130]
        assert [e['time'] for e in finishes]==[t+duration for t in times if t+duration<=130]
        assert s.ctx.get('enemy',('runtime','blocked_by'))==s.session.world.resolve('first')
        assert 'sp' not in s.ctx.entity('enemy')['components']['resources']
    return details
def transition(v):
    s=cpp(fixture(v['prefab_key'],change=True),'public-withdraw-new-target',cut=45,end=150);hits=ev(s,'damage.accepted');first=s.session.world.resolve('first');second=s.session.world.resolve('second')
    assert not s.ctx.active(first) and s.ctx.active(second);assert any(h['payload']['target']==first for h in hits) and any(h['payload']['target']==second for h in hits)
    assert all(h['time']<40 for h in hits if h['payload']['target']==first);assert all(h['time']>=60 for h in hits if h['payload']['target']==second)
    assert s.ctx.get('enemy',('runtime','blocked_by'))==second;assert s.ctx.resources.current(second,'sp')==7
    return {'hits':hits,'withdrawn':first,'public_new_target':second,'second_HP':s.ctx.resources.current(second,'hp')}
def multiple(v):
    s=cpp(fixture(v['prefab_key'],multi=True),'multiple-blocked-sources');sources=[s.session.world.resolve(x) for x in ('enemy','enemy2')];target=s.session.world.resolve('first');hits=ev(s,'damage.accepted');amount=oracle(v)['atk']-83
    assert all(s.ctx.get(x,('runtime','blocked_by'))==target for x in sources);assert set(h['payload']['source'] for h in hits)==set(sources)
    assert s.ctx.resources.current(target,'hp')==11731-len(hits)*amount
    return {'sources':sources,'actual_target':target,'hits':hits,'HP':s.ctx.resources.current(target,'hp')}
def main():
    source=json.loads(SOURCE.read_bytes());guards={str(p):sha(p) for p in [SOURCE,MODULE,*[p for p in (ROOT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]]};variants=list(source['variants'].values())
    assert sha(SOURCE)=='ad8a610ad5b3fbebe16a000f5098084accab4a346492dd686e937f22925fe360'
    jobs=[]
    for v in variants:
        if oracle(v)['hit_frame'] is not None:jobs.append((v['prefab_key']+'/speed1.25-reference-clock',lambda v=v:numerical(v,1.25)))
    ground=next(v for v in variants if v['prefab_key']=='enemy_1007_slime');jobs.append(('public-withdraw-new-target-correct-roster',lambda:transition(ground)))
    for label,fn in jobs:
        try:details=fn();ROWS.append({'case':label,'passed':True,'details':details})
        except Exception as e:ROWS.append({'case':label,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
        print(json.dumps({'case':label,'passed':ROWS[-1]['passed']}),flush=True);gc.collect()
    result={'schema':'ark-sim/chapter0-independent-numerical-peer/v1','core':implementation_digest(),'passed':all(r['passed'] for r in ROWS),'cases':ROWS,'full_disk_CP_head':PROOFS,'source_guards':guards,'source_unchanged':all(sha(p)==h for p,h in guards.items()),
      'test_profile':{'HP':11731,'DEF':83,'MRES':[17,61],'SP':7,'speed_override':1.25,'source_abilities_preserved':True},'scope':'Native constant mode eight consumers; numerical and reference target policy; no whole-stage or client acceptance','whole_stage':False,'client_verified':False}
    result['animation_speed_source_gap']='Native body linking attackSpeed to animation time is unavailable; standard reference clock retains exact declared hit/full frames while scaling interval. v1 rejected the alternative speed-scaled oracle.'
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'actual.v2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return 0 if result['passed'] and result['source_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
