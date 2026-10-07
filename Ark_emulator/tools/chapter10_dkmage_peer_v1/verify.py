"""Independent complete dkmage source consumer gates on frozen joint core."""
import copy,gc,hashlib,json,os,random,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];FREEZE=ROOT/'validation/campaign/chapter10_dkmage_source_v1/freeze.v1.json'
FROZEN=json.loads(FREEZE.read_bytes());CAND=Path(FROZEN['candidate'])
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.chapter10_dkmage_source_v1.build import build,providers,BODY,EMPTY
from tools.chapter10_bloodline_v1.build import entity_id
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter10_dkmage_peer_v1/result.v1.json'
N=0;ROWS=[];PROOFS=[];FACTS={};SEED=73019
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def scene():
    p=build()
    # Independently owned receiver definitions and scalar capacity/loss rules.
    rules={}
    for key,expr in [('capacity','inputs.parameters.capacity'),('loss','inputs.request.raw_amount'),('recovery','inputs.current'),('break_duration','inputs.parameters.break_duration_seconds'),('eligibility','True')]:
        rid='rule/peer/dkmage/'+key;rules['elemental.'+key]=rid
        p['rules'].append({'id':rid,'kind':'rule','contract':'elemental.'+key,'implementation':{'type':'expression','expression':expr}})
    profile={'capacity':9000,'resistance':0,'recovery_rate':0,'break_duration_seconds':1,
      'rules':{k:v for k,v in rules.items() if k!='elemental.eligibility'},'on_break':[],'on_end':[]}
    initial=[{'definition':BODY,'instanceAlias':'mage','position':{'row':4,'col':1}}]
    for i in range(6):
        target={'id':'unit/peer/dkmage/receiver'+str(i),'kind':'entity','tags':['player','receiver'+str(i)],'components':{
          'attributes':{'base':{'max_hp':12000,'atk':0,'def':37,'mres':20}},
          'resources':{'hp':{'initial':12000,'capacity':12000,'role':'health'}},
          'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'spatial':{},
          'elemental':{'eligibility_rule':rules['elemental.eligibility'],'elements':{'DARK':copy.deepcopy(profile)}},
          'lifecycle':{'policy':'policy/ark_lifecycle'}}}
        p['entities'].append(target);initial.append({'definition':target['id'],'instanceAlias':'r'+str(i),'position':{'row':4,'col':2.1+1.1*i}})
    p['scenarioDraft']={'id':'scene/peer/dkmage/source','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':13},'initialEntities':initial,'commands':[]}
    return p
def make(p,label):
    global N;N+=1;reg=providers()
    return Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=SEED,event_journal_path=LOG/(str(N)+'_'+label+'.active.jsonl'))
def events(s,kind):return [thaw(e) for e in s.session.events if e['type']==kind]
def cpp(s,cut,end,label):
    s.advance(cut-s.session.time);disk=write_checkpoint(s,LOG/(str(N)+'_'+label+'.checkpoint.json'))
    r=Engine.restore(s.program,load_checkpoint(disk),providers=providers())
    s.advance(end-s.session.time);r.advance(end-r.session.time)
    h=replay(s.program,s.export_replay(),providers=providers(),event_journal_path=LOG/(str(N)+'_'+label+'.head.active.jsonl'))
    obs=[observations(x,LOG/(str(N)+'_'+label+'_'+name+'.events.jsonl')) for x,name in [(s,'forward'),(r,'CP'),(h,'head')]]
    keys=('snapshot','events','event_count','continuation_state');equal=lambda o:all(o[k]==obs[0][k] for k in keys)
    cps=[thaw(x.checkpoint()) for x in (s,r,h)];full_equal=cps[0]==cps[1]==cps[2]
    proof={'label':label,'cut':cut,'end':end,'disk_sha256':disk['sha256'],'event_reference':disk['event_reference'],
      'observations':[{k:o[k] for k in keys} for o in obs],'disk_CP_equal':equal(obs[1]),'head_equal':equal(obs[2]),
      'full_checkpoint_equal':full_equal,'full_checkpoint_digests':[digest(c) for c in cps]}
    PROOFS.append(proof);assert equal(obs[1]) and equal(obs[2]) and full_equal,json.dumps(proof)
    return s
def source_identity():
    p=build();saved=json.loads(Path(FROZEN['module']['path']).read_bytes());assert p==saved
    meta=p['manifest']['metadata'];variant=meta['native_variant'];pref=meta['native_prefab'];nodes=variant['modes'][0]['nodes']
    assert nodes['_combat']['path_id']==nodes['_attack']['path_id']
    row=variant['native_enemy']['raw_rows'][0]['enemyData'];assert row['skills'] is None and row['spData'] is None
    body=next(e for e in p['entities'] if e['id']==BODY)
    assert body['components']['abilities']==['ability/c10/dkmage_chain'] and 'sp' not in body['components']['resources']
    owned=body['components']['lifecycle']['parameters']['native_owned_data'][EMPTY]
    assert owned['class']=='EmptyAbility' and owned['path_id']==5653700696913435974 and owned['blackboard']['epdamage.attack@ep_damage_ratio']==.3
    assert not any(k in owned['raw'] for k in ('_cooldown','_duration','_spData','_timeline')) and owned['raw']['_selector']['m_PathID']==0
    raw=next(c['raw'] for c in pref['components'].values() if c['native_class']=='AdvancedSelector');expected={k:v for k,v in raw.items() if k.startswith('_')}
    sels=[s for s in p['selectors'] if s['id'].startswith('selector/c10/dkmage_chain/')]
    assert len(sels)==2 and all(s['eligibility']['parameters']['source_configuration']==expected for s in sels)
    assert expected['_postFilter']==4 and expected['_abnormalFlag']==25 and expected['_abnormalCombo']==2 and expected['_excludeAbnormalFlag']==46
    assert expected['_targetMotion']==3 and expected['_targetCategory']==1
    action=body['components']['lifecycle']['death_spawns']['actions'][0]
    assert action['definition']==entity_id('enemy_1221_dzomg_2') and action['delay_seconds']==1 and action['count']==1
    FACTS['source_identity']={'selector_configuration':expected,'native_ability_alias_path':nodes['_combat']['path_id'],
      'owned_empty':owned,'owned_abilities':body['components']['abilities'],'DB_skills':None,'DB_spData':None,'death_action':action}
def four():
    s=cpp(make(scene(),'four'),43,100,'four')
    for i in range(4):
        atk=550*.85**i
        assert abs(s.ctx.resources.current('r'+str(i),'hp')-(12000-atk*.8))<1e-9
        assert abs(s.ctx.get('r'+str(i),('runtime','elemental','remaining','DARK'))-(9000-atk*.3))<1e-9
    for i in (4,5):assert s.ctx.resources.current('r'+str(i),'hp')==12000
    hits=events(s,'projectile.hit');assert len(hits)==4 and len({e['payload']['target'] for e in hits})==4
    starts=[e for e in events(s,'ability.started') if e['payload']['source']==2]
    ends=[e for e in events(s,'ability.finished') if e['payload']['source']==2]
    assert starts[0]['time']==0 and ends[0]['time']==66 and events(s,'projectile.launched')[0]['time']==37
    assert len(starts)==1 and s.ctx.get('mage',('abilities',))==['ability/c10/dkmage_chain']
    FACTS['four']={'hit_ticks':[e['time'] for e in hits],'HP':[s.ctx.resources.current('r'+str(i),'hp') for i in range(6)],
      'EP':[s.ctx.get('r'+str(i),('runtime','elemental','remaining','DARK')) for i in range(6)],'cast_start':0,'cast_end':66,'launch':37}
    s=cpp(make(scene(),'cycle'),159,200,'cycle');launches=events(s,'projectile.launched')
    assert [e['time'] for e in launches]==[37,157]
    FACTS['cycle']={'launches':[e['time'] for e in launches],'cycle_ticks':120}
def control(p,key,e,at):
    definition=p['entities'][-1];aid='ability/peer/dkmage/'+key
    definition['components'].setdefault('abilities',[]).append(aid)
    p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual','on_start':[e]},'timeline':[]})
    p['scenarioDraft']['commands'].append({'at':at,'action':'skill','source':'r5','ability':aid})
def current_attributes():
    p=scene();p['buffs'].extend([{'id':'buff/peer/dkmage/atk','kind':'buff','duration_seconds':8,'modifiers':[{'attribute':'atk','layer':'flat','value':150}]},
      {'id':'buff/peer/dkmage/res','kind':'buff','duration_seconds':8,'modifiers':[{'attribute':'mres','layer':'flat','value':-20}]}])
    control(p,'atk',{'op':'apply_buff','target':2,'buff':'buff/peer/dkmage/atk'},41)
    control(p,'res',{'op':'apply_buff','target':4,'buff':'buff/peer/dkmage/res'},43)
    s=cpp(make(p,'current'),41,100,'current')
    FACTS['current_reads']={'HP':[s.ctx.resources.current('r'+str(i),'hp') for i in range(4)],'EP':[s.ctx.get('r'+str(i),('runtime','elemental','remaining','DARK')) for i in range(4)],
      'commands_rejected':events(s,'command.rejected'),'buff_events':events(s,'buff.applied'),'hits':events(s,'projectile.hit')}
    for i in range(4):
        atk=(550 if i==0 else 700)*.85**i;amount=atk*(1 if i==1 else .8)
        assert abs(s.ctx.resources.current('r'+str(i),'hp')-(12000-amount))<1e-9
        assert abs(s.ctx.get('r'+str(i),('runtime','elemental','remaining','DARK'))-(9000-atk*.3))<1e-9
def selection():
    facts=[]
    for key,update,accepted in [('air',{'motion':2},True),('category4',{'category':4},False),
      ('target_free',{'target_free':True},False),('camouflage',{'abnormal_flags':[17]},False),('invisible',{'abnormal_flags':[9]},False)]:
        p=scene()
        for t in p['entities'][-6:]:t['components']['selection_state'].update(update)
        s=cpp(make(p,key),38,60,key);launch=events(s,'projectile.launched')
        assert bool(launch)==accepted
        if accepted:assert len(events(s,'projectile.hit'))==4
        facts.append({'case':key,'accepted':accepted,'launch_count':len(launch)})
    FACTS['selection']=facts
def missing_container():
    facts=[]
    for field in ('absent','class','path_id'):
        p=scene();body=next(e for e in p['entities'] if e['id']==BODY);owned=body['components']['lifecycle']['parameters']['native_owned_data']
        if field=='absent':owned.clear()
        elif field=='class':owned[EMPTY]['class']='FakeAbility'
        else:owned[EMPTY]['path_id']=-1
        s=make(p,'missing_'+field);s.advance(40);before=[s.ctx.resources.current('r0','hp'),s.ctx.get('r0',('runtime','elemental','remaining','DARK'))]
        try:s.advance(1)
        except (ValueError,RuntimeError,KeyError) as error:
            after=[s.ctx.resources.current('r0','hp'),s.ctx.get('r0',('runtime','elemental','remaining','DARK'))]
            assert before==after,'Failed native packet altered actual health/EP'
            facts.append({'field':field,'error':str(error),'health_EP_atomic_unchanged':True})
        else:raise AssertionError('Missing or mismatched native owned container accepted')
    FACTS['native_owned_refusal']=facts
def death_scene():
    p=scene();killer=p['entities'][-1];killer['components']['attributes']['base']['atk']=16001
    aid='ability/peer/dkmage/kill';killer['components']['abilities']=[aid]
    p['selectors'].append({'id':'selector/peer/dkmage/kill','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['definition_id'],'equals':BODY}},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/dkmage/kill','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    keeper=copy.deepcopy(killer);keeper['id']='unit/peer/dkmage/keeper';keeper['tags']=['enemy','keeper'];keeper['components'].pop('elemental');keeper['components']['abilities']=[];keeper['components']['selection_state']['side']=1;p['entities'].append(keeper)
    route={'motionMode':'WALK','startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':10},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':4,'position':{'row':1,'col':1}}]}
    keeper_route={'motionMode':'WALK','startPosition':{'row':6,'col':1},'endPosition':{'row':6,'col':10},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':5,'position':{'row':6,'col':1}}]}
    draft=p['scenarioDraft'];draft.update(initialEntities=[{'definition':killer['id'],'instanceAlias':'killer','position':{'row':7,'col':12}}],
      resources={'life':{'initial':999,'capacity':999}},objectives={'type':'waves','life_resource':'life'},commands=[{'at':11,'action':'skill','source':'killer','ability':aid}],
      timeline={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[
        {'kind':'spawn','spawn':{'definition':BODY,'instanceAlias':'mage','position':{'row':1,'col':1},'route':route},'count':1,'managed':True,'blocks_wave':True},
        {'kind':'spawn','spawn':{'definition':keeper['id'],'instanceAlias':'keeper','position':{'row':6,'col':1},'route':keeper_route},'count':1,'managed':True,'blocks_wave':True}]}]}]})
    return p
def death():
    p=death_scene();s=make(p,'death');s.advance(12);assert s.ctx.state()['kills']==1 and s.ctx.state()['pending_waves']==1 and not s.ctx.state()['finished']
    s=cpp(s,23,70,'death');born=events(s,'descendant.born');assert len(born)==1 and born[0]['time']==41
    child=s.ctx.entity(born[0]['payload']['child']);assert child['definition_id']==entity_id('enemy_1221_dzomg_2')
    assert child['components']['spatial']['movement']['wait_until']==120
    assert child['components']['spatial']['route']['endPosition']=={'row':1,'col':10}
    members=s.ctx.state()['timeline']['members'];assert members[str(child['id'])]['wave']==members[str(s.session.world.resolve('keeper'))]['wave']==0
    assert s.ctx.state()['pending_waves']==0 and not s.ctx.state()['finished'] and s.ctx.active('keeper')
    stream='ch10/bloodline/descendants';samples=[r for r in thaw(s.session.random.snapshot())['samples'] if r['stream']==stream];assert len(samples)==2
    seed=int.from_bytes(hashlib.sha256(json.dumps([SEED,stream],ensure_ascii=False,separators=(',',':')).encode()).digest(),'big')
    rng=random.Random(seed);expected_values=[rng.random(),rng.random()]
    assert [r['value'] for r in samples]==expected_values
    pos=born[0]['payload']['position'];bound=.10000000149011612
    assert all(pos[axis]==1+(2*value-1)*bound for axis,value in zip(('row','col'),expected_values))
    FACTS['death']={'death_tick':11,'birth_tick':41,'definition':child['definition_id'],'position':pos,'named_RNG':samples,
      'wait_until':120,'wave':members[str(child['id'])]['wave'],'pending':0,'same_wave_keeper_active':True,'child':thaw(child)}
def main():
    assert implementation_digest()==FROZEN['core']
    guards={str(CAND/p):h for p,h in FROZEN['candidate_inventory'].items()}
    for row in [FROZEN['module'],FROZEN['source_closure'],*FROZEN['helpers'],*FROZEN['dependencies']]:guards[row['path']]=row['sha256']
    assert all(sha(p)==h for p,h in guards.items())
    for name,fn in [('complete_native_source_identity',source_identity),('four_impacts_37_66_120tick_cycle',four),('source_target_current_HP_EP_reads',current_attributes),
      ('full_selector_air_category4_flags',selection),('native_owned_empty_data_refusal',missing_container),('public_death11_birth41_route_wave_RNG_keeper',death)]:
        try:fn();ROWS.append({'case':name,'passed':True})
        except Exception as e:ROWS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
        finally:print(json.dumps(ROWS[-1]),flush=True);gc.collect()
    result={'schema':'ark-sim/dkmage-source-independent-peer/v1','passed':all(r['passed'] for r in ROWS),'core':implementation_digest(),'freeze_sha256':sha(FREEZE),
      'source_guards':guards,'source_unchanged':all(sha(p)==h for p,h in guards.items()),'cases':ROWS,'facts':FACTS,'actual_CP_head_proofs':PROOFS,'peer_sha256':sha(__file__),
      'scope':'Selected native source body/owned data, declared selector reference model, finite attack chain and owned delayed death birth only; native EmptyAbility name does not establish an independently empty skill/cast. Native method body, whole-stage and client accuracy remain unverified.',
      'whole_stage_approval':False,'client_verified':False,'core_elemental_restore_gap_not_promoted':True}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return 0 if result['passed'] and result['source_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
