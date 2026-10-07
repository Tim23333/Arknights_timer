"""Independent source3 scene/oracles; exact parent9a and optional successor94."""
import argparse,copy,gc,hashlib,json,os,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];LOCK=ROOT/'validation/campaign/chapter10_stage17_ordinary_v1/freeze.v1.json'
OUT=ROOT/'validation/campaign/chapter10_stage17_ordinary_peer_v1';N=0;FACTS={};ROWS=[];PROOFS=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def receptor(mode='normal'):
    hp=17 if mode=='overkill' else 9877
    return {'id':'unit/peer/ordinary/player','kind':'entity','tags':['player','ground'],'components':{
      'attributes':{'base':{'max_hp':hp,'atk':397,'def':7777 if mode=='postRES' else 53,'mres':63 if mode=='postRES' else 23,'block_count':1}},
      'resources':{'hp':{'role':'health','initial':hp,'capacity':hp},**({'barrier':{'initial':413,'capacity':413}} if mode=='barrier' else {})},
      'spatial':{'blocking':True},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},
      'deployable':{'base_cost':0,'terrain':'ground','capacity':1,'cooldown_seconds':0},
      'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}}
def reception(inputs,params,context):
    result=thaw(inputs['effect']['settlement'])
    if params['mode']=='barrier':result['allocations']=[{'resource':'barrier','amount':result['amount']},{'resource':'hp','amount':0}]
    else:result['amount']=0;result['allocations']=[]
    return result
def registry():return {**providers(),'peer.ordinary.reception':{'callable':reception,'version':'explicit-health-only-barrier-or-zero-reference-v1'}}
def scene(key,mode='normal'):
    p=build(key);p['entities'].append(receptor(mode));source=next(e for e in p['entities'] if e['id']==entity_id(key))
    p['scenarioDraft']={'id':'scene/peer/ordinary/'+key+'/'+mode,'ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':11},
      'initialEntities':[{'definition':'unit/peer/ordinary/player','instanceAlias':'player','position':{'row':2,'col':2}},
        {'definition':source['id'],'instanceAlias':'source','position':{'row':2,'col':2},'route':{'motionMode':'WALK','startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':10},'checkpoints':[]}}],'commands':[]}
    if mode in ('barrier','invuln_reference'):
        rid='rule/peer/ordinary/reception';bid='buff/peer/ordinary/reception'
        p['rules'].append({'id':rid,'kind':'rule','contract':'damage.pipeline','parameters':{'mode':mode},'implementation':{'type':'provider','provider':'peer.ordinary.reception'}})
        p['buffs'].append({'id':bid,'kind':'buff','damage_hooks':[{'phase':'after','rule':rid}],**({'selection_flags':{'abnormal_flags':[5]}} if mode=='invuln_reference' else {})})
        p['entities'][-1]['components']['buffs']={'initial':[bid]}
    return p,source
def control(p,key,effect,at):
    player=next(e for e in p['entities'] if e['id']=='unit/peer/ordinary/player');aid='ability/peer/ordinary/'+key
    player['components']['abilities'].append(aid)
    p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]})
    p['scenarioDraft']['commands'].append({'at':at,'action':'skill','source':'player','ability':aid})
def create(p,label):
    global N;N+=1;reg=registry()
    return Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=12261729,event_journal_path=LOG/(str(N)+'_'+label+'.active.jsonl'))
def events(s,key):return [thaw(e) for e in s.session.events if e['type']==key]
def cpp(s,cut,end,label):
    s.advance(cut-s.session.time);disk=write_checkpoint(s,LOG/(str(N)+'_'+label+'.checkpoint.json'))
    r=Engine.restore(s.program,load_checkpoint(disk),providers=registry());assert thaw(s.checkpoint())==thaw(r.checkpoint())
    s.advance(end-s.session.time);r.advance(end-r.session.time)
    h=replay(s.program,s.export_replay(),providers=registry(),event_journal_path=LOG/(str(N)+'_'+label+'.head.active.jsonl'))
    obs=[observations(v,LOG/(str(N)+'_'+label+'_'+name+'.events.jsonl')) for v,name in [(s,'forward'),(r,'CP'),(h,'head')]]
    keys=('snapshot','events','event_count','continuation_state');equal=lambda v:all(v[k]==obs[0][k] for k in keys)
    cps=[thaw(v.checkpoint()) for v in (s,r,h)]
    proof={'label':label,'cut':cut,'end':end,'checkpoint_sha256':disk['sha256'],'event_reference':disk['event_reference'],
      'observations':[{k:v[k] for k in keys} for v in obs],'disk_CP_equal':equal(obs[1]),'head_equal':equal(obs[2]),
      'full_checkpoint_equal':cps[0]==cps[1]==cps[2],'full_digests':[digest(v) for v in cps]}
    PROOFS.append(proof);assert proof['disk_CP_equal'] and proof['head_equal'] and proof['full_checkpoint_equal'],json.dumps(proof)
    return s
def provenance():
    facts=[]
    for key in ('enemy_1229_darmy','enemy_1228_dslime','enemy_1226_dklord'):
        p=build(key);saved=next(r for r in FREEZE['modules'] if key in Path(r['path']).name)
        assert p==json.loads(Path(saved['path']).read_bytes())
        v=p['manifest']['metadata']['native_variant'];body=next(e for e in p['entities'] if e['id']==entity_id(key))
        a=v['native_enemy']['resolved']['attributes'];base=body['components']['attributes']['base']
        assert base['max_hp']==a['maxHp'] and base['atk']==a['atk'] and base['mres']==a['magicResistance']
        ability=next(r for r in p['abilities'] if r['id'] in body['components']['abilities'] and r['activation']['mode']=='automatic_attack')
        native=v['modes'][0]['nodes']['_combat'];assert ability['metadata']['native_combat']==native
        facts.append({'key':key,'HP':a['maxHp'],'ATK':a['atk'],'native_hit_frame':round(native['animation_binding']['events'][0]['seconds']*30),'full_frame':round(native['animation_binding']['duration']['seconds']*30)})
    FACTS['source_identity']=facts
def darmy():
    p,source=scene('enemy_1229_darmy')
    rules={}
    for k,c,expr in [('capacity','elemental.capacity','inputs.parameters.capacity'),('loss','elemental.loss','inputs.request.raw_amount'),('recovery','elemental.recovery','inputs.current'),('duration','elemental.break_duration','inputs.parameters.break_duration_seconds'),('eligibility','elemental.eligibility','True')]:
        rid='rule/peer/darmy/'+k;rules[c]=rid;p['rules'].append({'id':rid,'kind':'rule','contract':c,'implementation':{'type':'expression','expression':expr}})
    player=next(e for e in p['entities'] if e['id']=='unit/peer/ordinary/player')
    player['components']['elemental']={'eligibility_rule':rules['elemental.eligibility'],'elements':{'DARK':{'capacity':2849,'resistance':0,'recovery_rate':0,'break_duration_seconds':13/30,
      'rules':{k:v for k,v in rules.items() if k!='elemental.eligibility'},'on_break':[],'on_end':[]}}}
    p['buffs'].extend([{'id':'buff/peer/darmy/atk','kind':'buff','duration_seconds':3,'modifiers':[{'attribute':'atk','layer':'flat','value':37}]},
      {'id':'buff/peer/darmy/res','kind':'buff','duration_seconds':3,'modifiers':[{'attribute':'mres','layer':'flat','value':17}]}])
    control(p,'atk',{'op':'apply_buff','target':3,'buff':'buff/peer/darmy/atk'},10)
    control(p,'res',{'op':'apply_buff','target':2,'buff':'buff/peer/darmy/res'},12)
    s=cpp(create(p,'darmy'),16,40,'darmy')
    native=p['manifest']['metadata']['native_variant']['native_enemy']['resolved'];bb={r['key']:r['value'] for r in native['talentBlackboard']}
    atk=native['attributes']['atk']+37;res=23+17;expected=atk*(1-res/100);ep=atk*bb['epdamage.attack@ep_damage_ratio']
    assert abs(s.ctx.resources.current('player','hp')-(9877-expected))<1e-9
    assert abs(s.ctx.get('player',('runtime','elemental','remaining','DARK'))-(2849-ep))<1e-9
    damage=[e for e in events(s,'damage.accepted') if e['payload']['source']==3];assert len(damage)==1
    start=next(e for e in events(s,'ability.started') if e['payload']['source']==3)
    frame=round(native['attributes']['attackSpeed']*0+p['manifest']['metadata']['native_variant']['modes'][0]['nodes']['_combat']['animation_binding']['events'][0]['seconds']*30)
    assert damage[0]['time']-start['time']==frame and s.ctx.get('source',('runtime','blocked_by'))==2
    FACTS['darmy']={'actual_HP':s.ctx.resources.current('player','hp'),'actual_EP':s.ctx.get('player',('runtime','elemental','remaining','DARK')),
      'expected_health_loss':expected,'expected_EP_loss':ep,'hit_frame_after_cast':frame,'events':damage}
    p,_=scene('enemy_1229_darmy');p['scenarioDraft']['initialEntities'][1]['position']={'row':5,'col':1};p['scenarioDraft']['initialEntities'][1]['route']={'motionMode':'WALK','startPosition':{'row':5,'col':1},'endPosition':{'row':5,'col':10},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':3,'position':{'row':5,'col':1}}]}
    s=cpp(create(p,'unblocked'),16,40,'unblocked');assert not events(s,'damage.accepted')
def slime_boundaries():
    facts=[]
    for mode in ('normal','postRES','overkill','barrier','invuln_reference','heal_immunity','healing_bound'):
        p,source=scene('enemy_1228_dslime',mode);injury=9 if mode=='healing_bound' else 397
        control(p,'injure',{'op':'damage','target':3,'damage_type':'true','additions':injury,'scale':0},0)
        if mode=='heal_immunity':source['components']['resources']['hp']['parameters']={'healing_allowed':False}
        native=p['manifest']['metadata']['native_variant']['native_enemy']['resolved'];bb={r['key']:r['value'] for r in native['talentBlackboard']}
        damage=native['attributes']['atk']*(1-(63 if mode=='postRES' else 23)/100)
        primary=0 if mode in ('barrier','invuln_reference') else min(17 if mode=='overkill' else 9877,damage)
        healed=0 if mode=='heal_immunity' else min(injury,primary*bb['vampire.heal_scale'])
        s=create(p,mode);s.advance(4);assert s.ctx.resources.current('source','hp')==native['attributes']['maxHp']-injury
        s=cpp(s,4,12,mode)
        hits=[e for e in events(s,'damage.accepted') if e['payload']['source']==3];assert len(hits)==1 and abs(hits[0]['payload']['amount']-primary)<1e-8
        assert abs(s.ctx.resources.current('source','hp')-(native['attributes']['maxHp']-injury+healed))<1e-8
        if mode=='barrier':assert abs(s.ctx.resources.current('player','barrier')-(413-damage))<1e-8
        if mode=='heal_immunity':assert events(s,'healing.rejected')
        facts.append({'mode':mode,'primary_health_delta':hits[0]['payload']['amount'],'expected_primary':primary,'heal':healed,'source_HP':s.ctx.resources.current('source','hp'),
          'policy':'Explicit reception hook with actual flag5 for invuln; actual primary-health output reference, not client method body' if mode=='invuln_reference' else 'Declared primary-health output reference'})
    FACTS['slime_boundaries']=facts
def slime_marker_removal():
    p,source=scene('enemy_1228_dslime');control(p,'injure',{'op':'damage','target':3,'damage_type':'true','scale':0,'additions':397},0)
    control(p,'remove',{'op':'remove_buff','target':3,'buff':VAMPIRE},9)
    s=cpp(create(p,'marker'),8,30,'marker')
    hits=[e for e in events(s,'damage.accepted') if e['payload']['source']==3];assert len(hits)==2
    expected=4000-397+90*.77*2.2;assert abs(s.ctx.resources.current('source','hp')-expected)<1e-8
    assert not any(e['payload']['amount']>0 and e['time']>9 for e in events(s,'healing.accepted'))
    FACTS['slime_marker']={'HP':s.ctx.resources.current('source','hp'),'hit_ticks':[e['time'] for e in hits],'no_positive_heal_after_public_removal':True}
def lord_scene(count):
    p,source=scene('enemy_1226_dklord');player=next(e for e in p['entities'] if e['id']=='unit/peer/ordinary/player')
    player['components']['attributes']['base']['def']=197
    marked={'id':'unit/peer/ordinary/marked','kind':'entity','tags':['enemy','marked'],'components':{
      'attributes':{'base':{'max_hp':971,'atk':0,'def':0,'mres':0}},'resources':{'hp':{'role':'health','initial':971,'capacity':971}},
      'selection_state':{'side':1,'category':1,'motion':1},'buffs':{'initial':['buff/ch10/bloodline/bloodsucker_mark']},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    p['entities'].append(marked)
    for i in range(count):p['scenarioDraft']['initialEntities'].append({'definition':marked['id'],'instanceAlias':'member'+str(i),'position':{'row':6,'col':i+1}})
    for label,change in [('air',{'motion':2}),('unmarked',{})]:
        d=copy.deepcopy(marked);d['id']+='_'+label
        if label=='unmarked':d['components']['buffs']={'initial':[]}
        d['components']['selection_state'].update(change);p['entities'].append(d);p['scenarioDraft']['initialEntities'].append({'definition':d['id'],'instanceAlias':label,'position':{'row':5,'col':8 if label=='air' else 9}})
    return p,source
def lord_aura():
    facts=[]
    for count in (2,5,8):
        p,source=lord_scene(count)
        if count==8:
            for i,at in enumerate((40,42,44)):control(p,'depart'+str(i),{'op':'retire','target':4+i,'parameters':{'reason':'withdrawn'}},at)
        end=200 if count==8 else 60;s=cpp(create(p,'lord'+str(count)),30,end,'lord'+str(count))
        bb={r['key']:r['value'] for r in p['manifest']['metadata']['native_variant']['native_enemy']['resolved']['talentBlackboard']}
        initial_atk=1000*(1+bb['aura.atk']*min(int(bb['aura.max_valid_stack_cnt']),count))
        hits=[e for e in events(s,'damage.accepted') if e['payload']['source']==3]
        assert abs(hits[0]['payload']['amount']-(initial_atk-197))<1e-8
        if count==8:assert len(hits)==2 and abs(hits[1]['payload']['amount']-(1000*(1+bb['aura.atk']*5)-197))<1e-8
        actual=next(b for b in s.ctx.get('source',('buffs','instances')) if b['definition']==LORD)
        assert len(actual['aura_members'])==(5 if count==8 else count)
        facts.append({'members':count,'initial_ATK_from_raw_BB':initial_atk,'actual_hit_amounts':[e['payload']['amount'] for e in hits],
          'final_live_aura_members':len(actual['aura_members']),'unmarked_air_excluded':True})
    FACTS['lord_aura']=facts
def main():
    global Compiler,Engine,thaw,digest,replay,write_checkpoint,load_checkpoint,observations,build,providers,entity_id,LORD,VAMPIRE,LOG,FREEZE
    parser=argparse.ArgumentParser();parser.add_argument('--successor',type=Path);args=parser.parse_args()
    FREEZE=json.loads(LOCK.read_bytes());runtime=json.loads(args.successor.read_bytes()) if args.successor else FREEZE
    candidate=Path(runtime['candidate']);inv=runtime.get('candidate_inventory') or runtime['source_inventory'];guards={str(candidate/k):v for k,v in inv.items()}
    for r in [*FREEZE['modules'],*FREEZE['helpers'],*FREEZE['dependencies']]:guards[r['path']]=r['sha256']
    assert all(sha(p)==h for p,h in guards.items());sys.path.insert(0,str(candidate));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw,digest
    from ark_sim.tools.replay import replay
    from tools.chapter10_stage17_ordinary_v1.build import build,providers,entity_id,LORD,VAMPIRE
    from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
    assert implementation_digest()==runtime['core'];LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT.mkdir(parents=True,exist_ok=True)
    for name,fn in [('exact_frozen_source3_identity',provenance),('darmy_currentATK_RES_EP_native_hit_blocked_only',darmy),
      ('slime_primary_health_reference_boundaries_new_numbers',slime_boundaries),('slime_actual_source_marker_public_removal',slime_marker_removal),('lord_global_actual_mark_aura_count_cap_departures',lord_aura)]:
        try:fn();ROWS.append({'case':name,'passed':True})
        except Exception as e:ROWS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
        finally:print(json.dumps(ROWS[-1]),flush=True);gc.collect()
    result={'schema':'ark-sim/stage17-ordinary-independent-peer/v1','core':implementation_digest(),'source_freeze_sha256':sha(LOCK),
      'runtime_freeze_sha256':sha(args.successor) if args.successor else sha(LOCK),'source_unchanged':all(sha(p)==h for p,h in guards.items()),
      'source_guards':guards,'cases':ROWS,'facts':FACTS,'actual_CP_head_proofs':PROOFS,'passed':all(r['passed'] for r in ROWS),
      'reference_boundary':'Vampire uses actual primary capped health delta, including postRES/zero barrier/explicit invuln reception projection; native/client event equivalence remains unverified.',
      'dmech_runtime_claim':False,'whole_stage_approval':False,'client_verified':False,'primary_modified':False,'peer_sha256':sha(__file__)}
    dest=OUT/('result.94.v1.json' if args.successor else 'result.9a.v1.json');dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return 0 if result['passed'] and result['source_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
