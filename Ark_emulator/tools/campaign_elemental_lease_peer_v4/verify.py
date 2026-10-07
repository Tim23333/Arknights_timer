"""Independent hostile restore/transaction gates; requires an explicit final freeze."""
import argparse,copy,gc,hashlib,json,os,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'validation/campaign/campaign_elemental_lease_peer_v4'
ROWS=[];FACTS={};PROOFS=[];N=0
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def create(p,label):
    global N;N+=1;reg=fixture.registry()
    return Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=6131193,event_journal_path=LOG/(str(N)+'_'+label+'.active.jsonl'))
def obs(s,label):return observations(s,LOG/(str(N)+'_'+label+'.events.jsonl'))
def records(s,name):return [thaw(e) for e in s.session.events if e['type']==name]
def state(s,alias='receiver'):return s.ctx.get(alias,('runtime','elemental'))
def cpp(s,cut,end,label,reg=None):
    reg=reg or fixture.registry();s.advance(cut-s.session.time)
    disk=write_checkpoint(s,LOG/(str(N)+'_'+label+'.checkpoint.json'));loaded=load_checkpoint(disk)
    before=thaw(s.checkpoint());r=Engine.restore(s.program,loaded,providers=reg)
    assert thaw(r.checkpoint())==before,'Legal restore mutated full five-store/cache state'
    s.advance(end-s.session.time);r.advance(end-r.session.time)
    h=replay(s.program,s.export_replay(),providers=reg,event_journal_path=LOG/(str(N)+'_'+label+'.head.active.jsonl'))
    result=[obs(x,label+'_'+k) for x,k in [(s,'forward'),(r,'CP'),(h,'head')]]
    keys=('snapshot','events','event_count','continuation_state');equal=lambda v:all(v[k]==result[0][k] for k in keys)
    cps=[thaw(x.checkpoint()) for x in (s,r,h)]
    proof={'label':label,'cut':cut,'end':end,'checkpoint_sha256':disk['sha256'],'event_reference':disk['event_reference'],
      'observations':[{k:v[k] for k in keys} for v in result],'disk_CP_equal':equal(result[1]),'head_equal':equal(result[2]),
      'full_checkpoint_equal':cps[0]==cps[1]==cps[2],'full_digests':[digest(v) for v in cps]}
    PROOFS.append(proof);assert proof['disk_CP_equal'] and proof['head_equal'] and proof['full_checkpoint_equal'],json.dumps(proof)
    return s
def generic_legitimate():
    p=fixture.scene();fixture.request(p,'priorB',fixture.B,79,5)
    fixture.request(p,'breakA',fixture.A,4,9,packet_rule=True)
    fixture.request(p,'lockedB',fixture.B,1193,12)
    fixture.request(p,'nextB',fixture.B,1400,21)
    s=create(p,'generic');s.advance(10)
    assert state(s)['remaining']=={fixture.A:0,fixture.B:1114}
    assert state(s)['break']['due']==16 and state(s)['break']['provenance']['source_snapshot']['sampled_at']==9
    audit=[e for e in records(s,'elemental.state.record') if e['payload']['operation']=='loss'][-1]
    proofrows=audit['payload']['proofs'];packet=next(r for r in proofrows if r['contract']=='elemental.packet')
    assert packet['inputs']['source']['sampled_at']==packet['context']['time']==9
    assert packet['value']==724 and packet['runtime']==s.ctx.rules.fingerprint
    assert next(r for r in proofrows if r['contract']=='time.quantize')['scope']['owner']['time.quantize']=='rule/peer/ep/clock'
    s=cpp(s,10,34,'generic')
    assert state(s)['remaining']=={fixture.A:613,fixture.B:1193} and state(s)['break'] is None and state(s)['generation']==2
    assert [e['time'] for e in records(s,'elemental.break.ended')]==[16,32]
    assert not any(e['time']==12 for e in records(s,'elemental.loss.accepted'))
    FACTS['generic']={'profile_keys':[fixture.A,fixture.B],'capacities':[613,1193],'durations_ticks':[7,11],'ending':state(s),
      'provider_context_readonly_actual':True,'source_timestamp_actual':9,'runtime_fingerprint':s.ctx.rules.fingerprint}
def recovery_dynamic():
    p=fixture.scene(recovery=13);fixture.request(p,'lossB',fixture.B,79,5)
    s=cpp(create(p,'recovery'),8,12,'recovery')
    # Tick5 applies79 after the elemental system; ticks6..11 recover six times.
    assert abs(state(s)['remaining'][fixture.B]-(1193-79+6*13/30))<1e-9
    FACTS['recovery']={'remaining':state(s)['remaining'],'expected_B':1193-79+6*13/30}
    p=fixture.scene();p['buffs'].append({'id':'buff/peer/cap_delta','kind':'buff','duration_seconds':2,'modifiers':[{'attribute':'element_delta','layer':'flat','value':-10}]})
    fixture.ability(p,'delta',{'op':'apply_buff','target':2,'buff':'buff/peer/cap_delta'},4)
    fixture.request(p,'syncB',fixture.B,1,7)
    s=cpp(create(p,'capacity'),8,12,'capacity')
    assert state(s)['remaining']=={fixture.A:603,fixture.B:1182}
    FACTS['capacity_dynamic']={'remaining':state(s)['remaining']}
def hostile():
    p=fixture.scene();fixture.request(p,'break',fixture.A,4,9,packet_rule=True);s=create(p,'hostile');s.advance(10)
    base=thaw(s.checkpoint());facts=[]
    def actor(c):return next(e for e in c['kernel']['world']['entities'] if e['id']==2)
    def st(c):return actor(c)['components']['runtime']['elemental']
    def task(c):return next(t for t in c['kernel']['scheduler']['tasks'] if t['id']==st(c)['break']['task'])
    def event(c,ident):return next(e for e in c['kernel']['events']['records'] if e['id']==ident)
    def latest(c):return event(c,st(c)['audit_event'])['payload']
    def test(name,change):
        c=copy.deepcopy(base);change(c)
        try:Engine.restore(s.program,c,providers=fixture.registry())
        except (ValueError,KeyError,TypeError) as e:facts.append({'field':name,'actual_rejected':True,'error':str(e)})
        else:facts.append({'field':name,'actual_rejected':False})
    test('remaining',lambda c:st(c)['remaining'].__setitem__(fixture.A,1))
    for field in ('due','generation','task','seq'):test(field,lambda c,f=field:st(c)['break'].__setitem__(f,st(c)['break'][f]+1))
    test('provenance',lambda c:st(c)['break']['provenance']['request'].__setitem__('raw_amount',1))
    def coherent(c):
        st(c)['break']['due']+=1;task(c)['at']+=1
    test('coherent_due_and_queue',coherent)
    def duplicate(c):
        t=copy.deepcopy(task(c));queue=c['kernel']['scheduler'];t['id']=queue['next_id'];t['seq']=queue['next_seq'];queue['next_id']+=1;queue['next_seq']+=1;queue['tasks'].append(t)
    test('duplicate_expiry',duplicate)
    test('missing_expiry',lambda c:c['kernel']['scheduler'].__setitem__('tasks',[t for t in c['kernel']['scheduler']['tasks'] if t['id']!=st(c)['break']['task']]))
    def orphan(c):task(c)['payload']['target']=3
    test('orphan_expiry_target',orphan)
    test('false_audit_event',lambda c:st(c).__setitem__('audit_event',1))
    test('actor_stamp',lambda c:st(c)['break']['target_stamp'].__setitem__('lifecycle_generation',7))
    def dead(c):actor(c)['components']['runtime']['state']='dead';actor(c)['components']['runtime']['active']=False
    test('active_lease_after_death',dead)
    test('new_life_generation',lambda c:actor(c)['components']['runtime'].__setitem__('lifecycle_generation',9))
    test('all_bar_key_missing',lambda c:st(c)['remaining'].pop(fixture.B))
    test('all_bar_key_extra',lambda c:st(c)['remaining'].__setitem__('undeclared/extra',0))
    test('negative_bar',lambda c:st(c)['remaining'].__setitem__(fixture.B,-1))
    test('capacity_bound',lambda c:st(c)['remaining'].__setitem__(fixture.B,1194))
    test('nan_bar',lambda c:st(c)['remaining'].__setitem__(fixture.B,float('nan')))
    def coherent_remaining(c):
        st(c)['remaining'][fixture.A]=1;latest(c)['state']['remaining'][fixture.A]=1
    test('state_and_latest_record_remaining',coherent_remaining)
    def falseproof(c):
        row=next(p for p in latest(c)['proofs'] if p['contract']=='elemental.packet');row['value']+=1;event(c,row['event'])['payload']['value']+=1
    test('proof_and_calculation_value',falseproof)
    def sourceclock(c):
        row=next(p for p in latest(c)['proofs'] if p['contract']=='elemental.packet');row['context']['time']+=1
    test('historical_provider_context_time',sourceclock)
    def rulebinding(c):
        row=next(p for p in latest(c)['proofs'] if p['contract']=='time.quantize');row['scope']['owner']['time.quantize']='rule/peer/ep/capacity'
    test('historical_scope_binding',rulebinding)
    def trace(c):
        row=next(p for p in latest(c)['proofs'] if p['contract']=='elemental.packet');event(c,row['event'])['payload']['trace']={'forged':'full-trace'}
    test('full_calculation_trace',trace)
    def cause(c):
        row=next(p for p in latest(c)['proofs'] if p['contract']=='elemental.packet');event(c,row['event'])['cause']=1
    test('historical_calculation_cause',cause)
    test('initialized_owner_lost_profile',lambda c:actor(c)['components'].pop('elemental'))
    test('initialized_owner_lost_state',lambda c:actor(c)['components']['runtime'].pop('elemental'))
    test('declared_profile_capacity_changed',lambda c:actor(c)['components']['elemental']['elements'][fixture.A].__setitem__('capacity',614))
    FACTS['hostile']=facts;assert all(r['actual_rejected'] for r in facts),json.dumps([r for r in facts if not r['actual_rejected']])
def direct_scope():
    p=fixture.scene();fixture.request(p,'break',fixture.A,800,9);s=create(p,'direct');s.advance(10);before=thaw(s.checkpoint());lease=state(s)['break']
    s.ctx.elemental.expire(s.session,{'target':2,'generation':lease['generation']})
    assert thaw(s.checkpoint())==before
    try:s.ctx.elemental.callbacks(2,fixture.A,copy.deepcopy(lease),'on_break',lease.get('break_event'))
    except (ValueError,RuntimeError):pass
    else:raise AssertionError('Data-only lease/cause acquired callback capability')
    assert thaw(s.checkpoint())==before
    FACTS['direct_scope']={'expiry_noop_fullCP_equal':True,'callback_capability_actual_rejected':True}
def death_respawn():
    p=fixture.scene();fixture.request(p,'break',fixture.A,800,9)
    fixture.ability(p,'kill',{'op':'modify_resource','target':2,'resource':'hp','value':0},12)
    p['scenarioDraft']['commands'].append({'at':20,'action':'deploy','definition':'unit/peer/ep_receiver','alias':'receiver2','position':{'row':2,'col':2},'facing':'right'})
    s=cpp(create(p,'life'),13,24,'life')
    assert not s.ctx.active('receiver') and state(s)['break'] is None
    assert s.ctx.active('receiver2') and state(s,'receiver2')['remaining']=={fixture.A:613,fixture.B:1193} and state(s,'receiver2')['generation']==0
    assert not records(s,'peer.ep.end_actual')
    FACTS['life']={'old':state(s),'new':state(s,'receiver2'),'new_HP':s.ctx.resources.current('receiver2','hp')}
def stores(s):
    return {'world':thaw(s.session.world.snapshot()),'jobs':thaw(s.session.scheduler.snapshot()),'events':thaw(s.session._events.snapshot()),
      'RNG':thaw(s.session.random.snapshot()),'attribute_cache':{'causal_cache':thaw(s.ctx.attributes.checkpoint_cache()),
        'last_calculation_event_id':getattr(s.ctx,'last_calculation_event_id',None),'cache_time':s.ctx.attributes._cache_time}}
def fault_outer_transaction():
    p=fixture.scene(fault=True);fixture.request(p,'actual_fault',fixture.A,4,9,packet_rule=True,health=True)
    s=create(p,'fault');captured={};original_execute=s.ctx.effects.execute;original_emit=s.ctx.emit
    class Injected(RuntimeError):pass
    def emit(name,payload=None,cause=None):
        if name=='peer.ep.fault':
            captured['fault_inside']=stores(s)
            captured['actual_task']=thaw(s.session.current_task)
            raise Injected('Actual owned elemental break callback fault')
        return original_emit(name,payload,cause)
    def execute(source,targets,effect,*args,**kwargs):
        if effect.get('op')!='elemental_attack':return original_execute(source,targets,effect,*args,**kwargs)
        captured['before_outer']=stores(s)
        try:return original_execute(source,targets,effect,*args,**kwargs)
        except Injected:
            captured['after_outer']=stores(s)
            raise
    s.ctx.emit=emit;s.ctx.effects.execute=execute
    try:s.advance(10)
    except (Injected,RuntimeError) as error:
        assert captured.get('actual_task',{}).get('kind')=='domain.ability.effect'
        assert captured['before_outer']==captured['after_outer'],'Actual outer transaction failed five-store rollback'
        changed=[k for k in captured['before_outer'] if captured['before_outer'][k]!=captured['fault_inside'][k]]
        assert set(changed)==set(captured['before_outer']), 'Fault did not actually reach writes in all five stores: '+str(changed)
        FACTS['fault']={'actual_task':captured['actual_task'],'changed_inside':changed,'all_five_stores_rollback_equal':True,
          'before_digests':{k:digest(v) for k,v in captured['before_outer'].items()},'after_digests':{k:digest(v) for k,v in captured['after_outer'].items()},'error':str(error)}
    else:raise AssertionError('Declared fault callback did not execute')
def source_business_receiver():
    from tools.campaign_elemental_receivers_v1.build import mount,providers as business_providers
    roster=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json'
    buildpath=ROOT/'tools/campaign_elemental_receivers_v1/build.py';guards={str(p):sha(p) for p in (roster,buildpath)}
    definitions=copy.deepcopy(json.loads(roster.read_bytes())['definitions']);by={d['id']:d for d in definitions};target=by['unit/char_107_liskam']
    for aid in target['components']['abilities']:by[aid]['activation']['condition']='False'
    source={'id':'unit/peer/lease_business/source','kind':'entity','tags':['enemy'],'components':{
      'attributes':{'base':{'max_hp':1911,'atk':0,'def':0,'mres':0}},'resources':{'hp':{'role':'health','initial':1911,'capacity':1911}},
      'selection_state':{'side':1,'category':1,'motion':1},'spatial':{},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    definitions.append(source)
    p={'schemaVersion':2,'definitions':definitions,'scenarioDraft':{'id':'scene/peer/lease_business','ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':7},
      'initialEntities':[{'definition':target['id'],'instanceAlias':'receiver','position':{'row':2,'col':2}},{'definition':source['id'],'instanceAlias':'sender','position':{'row':2,'col':5}}], 'commands':[]}}
    actions=[(3,{'op':'modify_resource','target':2,'resource':'sp','value':18}),
      (5,{'op':'elemental_damage','target':2,'element':'DARK','amount':113}),
      (9,{'op':'elemental_damage','target':2,'element':'DARK','amount':1000}),
      (12,{'op':'elemental_damage','target':2,'element':'FIRE','amount':1000}),
      (15,{'op':'modify_resource','target':2,'resource':'sp','delta':5,'parameters':{'respect_recovery_freeze':True}})]
    for i,(at,effect) in enumerate(actions):
        aid='ability/peer/lease_business/'+str(i);source['components']['abilities'].append(aid)
        definitions.append({'id':aid,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]})
        p['scenarioDraft']['commands'].append({'at':at,'action':'skill','source':'sender','ability':aid})
    skill='ability/peer/lease_business/skill';target['components']['abilities'].append(skill)
    definitions.append({'id':skill,'kind':'ability','activation':{'mode':'manual','costs':[{'resource':'sp','amount':1}]},'timeline':[{'at':0,'effect':{'op':'emit','target':'source','event':'peer.business.skill','payload':{}}}]})
    for tick in (11,460):p['scenarioDraft']['commands'].append({'at':tick,'action':'skill','source':'receiver','ability':skill})
    mount(p,entities=[target['id']]);reg=business_providers()
    global N;N+=1
    s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=6131193,event_journal_path=LOG/(str(N)+'_business.active.jsonl'))
    s.advance(6);assert state(s)['remaining']['DARK']==887
    s=cpp(s,10,462,'business',reg=reg)
    hits=[e for e in records(s,'damage.accepted') if e['payload'].get('source_policy')=='none']
    assert [e['time'] for e in hits]==[9+30*i for i in range(15)] and all(e['payload']['source'] is None and e['payload']['ignore_for_sp'] for e in hits)
    assert s.ctx.resources.current('receiver','hp')==3124-15*90 and s.ctx.resources.current('receiver','sp')==2
    assert state(s)['remaining']=={'FIRE':1000,'DARK':1000} and state(s)['break'] is None
    assert any(e['time']==11 for e in records(s,'command.rejected')) and records(s,'peer.business.skill')[0]['time']==460
    assert any(e['time']==15 for e in records(s,'resource.recovery_suppressed'))
    assert all(sha(p)==h for p,h in guards.items())
    FACTS['business']={'source_guards':guards,'HP':s.ctx.resources.current('receiver','hp'),'SP':s.ctx.resources.current('receiver','sp'),
      'state':state(s),'NoSource_ticks':[e['time'] for e in hits],'source_none':True,'first113_EP887':True,'new_core_proof':True}
def main():
    global fixture,Compiler,Engine,thaw,digest,replay,write_checkpoint,load_checkpoint,observations,LOG
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',type=Path,required=True);args=parser.parse_args()
    manifest=json.loads(args.freeze.read_bytes());candidate=Path(manifest['candidate'])
    # No unfrozen runtime import or execution occurs before this explicit lock.
    expected=manifest.get('core') or manifest.get('implementation');assert expected
    inventory=manifest.get('candidate_inventory') or manifest.get('source_inventory');assert inventory,'Final full inventory required'
    guards={str(candidate/p):h for p,h in inventory.items()};assert all(sha(p)==h for p,h in guards.items())
    sys.path.insert(0,str(candidate));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw,digest
    from ark_sim.tools.replay import replay
    from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
    from tools.campaign_elemental_lease_peer_v4 import fixture
    assert implementation_digest()==expected;LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT.mkdir(parents=True,exist_ok=True)
    for name,fn in [('odd_keys_nonstandard_capacity_duration_packet_scope_fullFP',generic_legitimate),('nonzero_recovery_dynamic_capacity',recovery_dynamic),
      ('hostile_restore_original_six_and_coherent_fields',hostile),('direct_scope_private_capability_no_grant',direct_scope),
      ('death_cancel_new_actor_reset',death_respawn),('actual_owned_fault_outer_five_store_rollback',fault_outer_transaction),
      ('actual_source_business_receiver_rebased_new_core',source_business_receiver)]:
        try:fn();ROWS.append({'case':name,'passed':True})
        except Exception as e:ROWS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
        finally:print(json.dumps(ROWS[-1]),flush=True);gc.collect()
    result={'schema':'ark-sim/elemental-lease-independent-peer/v4','passed':all(r['passed'] for r in ROWS),'core':implementation_digest(),
      'freeze_path':str(args.freeze),'freeze_sha256':sha(args.freeze),'source_guards':guards,'source_unchanged':all(sha(p)==h for p,h in guards.items()),
      'cases':ROWS,'facts':FACTS,'actual_CP_head_proofs':PROOFS,'peer_sources':{str(p):sha(p) for p in Path(__file__).parent.glob('*.py')},
      'whole_stage_approval':False,'client_body_accuracy_verified':False,'primary_modified':False}
    (OUT/'result.v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return 0 if result['passed'] and result['source_unchanged'] else 1
if __name__=='__main__':
    try:code=main()
    except Exception as error:
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'bootstrap.failure.v1.json').write_text(json.dumps({'schema':'ark-sim/elemental-lease-peer-bootstrap-failure/v1',
          'passed':False,'actual_core_unverified':True,'error':str(error),'traceback':traceback.format_exc()},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps({'bootstrap_failed':True,'error':str(error)}),flush=True);code=2
    raise SystemExit(code)
