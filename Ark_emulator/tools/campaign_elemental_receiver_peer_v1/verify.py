"""Independent fixed roster receiver review with fresh disk CP/head evidence."""
import copy,gc,hashlib,json,os,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE
from tools.campaign_elemental_receivers_v1.build import module,mount,providers,DARK,FIRE,SOURCE,TABLE
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_elemental_receiver_peer_v1/result.v1.json'
ROSTER=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json';N=0;ROWS=[];PROOFS=[];FACTS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def package(target='unit/char_107_liskam',isolate=True):
    defs=copy.deepcopy(json.loads(ROSTER.read_bytes())['definitions']);by={d['id']:d for d in defs};actor=by[target]
    # Preserve original health, SP, owned skill definitions and events. Explicit
    # test condition isolates original actions only when the numerical gate needs it.
    if isolate:
        for aid in actor['components'].get('abilities',[]):by[aid]['activation']['condition']='False'
    source={'id':'unit/peer/element_source','kind':'entity','tags':['enemy','ground'],'components':{
      'attributes':{'base':{'max_hp':100000,'atk':0,'def':0,'mres':0}},
      'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},
      'selection_state':{'side':1,'category':1,'motion':1},'spatial':{},'abilities':[],
      'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    defs.append(source)
    d={'schemaVersion':2,'definitions':defs,'scenarioDraft':{'id':'scene/independent/element/'+target,'ruleset':'ruleset/ark_standard',
       'map':{'rows':6,'cols':9},'initialEntities':[{'definition':target,'instanceAlias':'receiver','position':{'row':3,'col':3}},
         {'definition':source['id'],'instanceAlias':'sender','position':{'row':3,'col':4}}], 'commands':[]}}
    return d,actor,source,by
def effect(d,source,e,at):
    aid='ability/peer/element/'+str(len(d['scenarioDraft']['commands']));source['components']['abilities'].append(aid)
    d['definitions'].append({'id':aid,'kind':'ability','activation':{'mode':'manual','on_start':[e]},'timeline':[]})
    d['scenarioDraft']['commands'].append({'at':at,'action':'skill','source':'sender','ability':aid})
def packet(d,source,key,amount,at):effect(d,source,{'op':'elemental_damage','target':2,'element':key,'amount':amount},at)
def finish(d,target):mount(d,entities=[target['id']]);return d
def make(d,label):
    global N;N+=1;registry=providers()
    return Engine.create(Compiler(providers=registry).compile(d),providers=registry,seed=71091,event_journal_path=LOG/(str(N)+'_'+label+'.active.jsonl'))
def events(s,kind):return [thaw(e) for e in s.session.events if e['type']==kind]
def state(s):return s.ctx.get('receiver',('runtime','elemental'))
def hp(s):return s.ctx.resources.current('receiver','hp')
def sp(s):return s.ctx.resources.current('receiver','sp')
def cpp(s,cut,end,label):
    s.advance(cut-s.session.time);cp=write_checkpoint(s,LOG/(str(N)+'_'+label+'.checkpoint.json'))
    r=Engine.restore(s.program,load_checkpoint(cp),providers=providers());s.advance(end-s.session.time);r.advance(end-r.session.time)
    h=replay(s.program,s.export_replay(),providers=providers(),event_journal_path=LOG/(str(N)+'_'+label+'.head.active.jsonl'))
    obs=[observations(x,LOG/(str(N)+'_'+label+'_'+k+'.events.jsonl')) for x,k in [(s,'forward'),(r,'CP'),(h,'head')]]
    keys=('snapshot','events','event_count','continuation_state')
    equal=lambda o:all(o[k]==obs[0][k] for k in keys)
    PROOFS.append({'label':label,'cut':cut,'end':end,'checkpoint_sha256':cp['sha256'],'event_reference':cp['event_reference'],
      'observations':[{k:o[k] for k in keys} for o in obs],'disk_CP_equal':equal(obs[1]),'head_equal':equal(obs[2])})
    assert equal(obs[1]) and equal(obs[2]),'Full disk CP/head observation mismatch: '+json.dumps(PROOFS[-1])
    return s
def basic():
    d,t,src,_=package('unit/char_151_myrtle');packet(d,src,'DARK',113,9);s=make(finish(d,t),'113');initial=hp(s)
    s=cpp(s,10,41,'113');assert state(s)['remaining']=={'FIRE':1000,'DARK':887} and hp(s)==initial
    FACTS['113']={'HP':hp(s),'EP':state(s)}
def fire():
    d,t,src,_=package();packet(d,src,'FIRE',1000,9);finish(d,t);s=make(d,'fire');initial=hp(s);before=s.ctx.attributes.value('receiver','mres')
    s.advance(10);after=s.ctx.attributes.value('receiver','mres');loss=1200*(1-max(0,min(100,after))/100)
    assert after==before-20 and hp(s)==initial-loss
    damage=events(s,'damage.accepted');assert len(damage)==1 and damage[0]['payload']['source'] is None and damage[0]['payload']['source_policy']=='none'
    assert damage[0]['payload']['ignore_for_sp'] is False
    FACTS['fire']={'mres_before':before,'mres_after':after,'HP_before':initial,'HP_after':hp(s),'SP_after':sp(s),'damage':damage}
    s=cpp(make(d,'fire_proof'),10,311,'fire');assert state(s)['remaining']=={'FIRE':1000,'DARK':1000} and state(s)['break'] is None
def dark():
    d,t,src,_=package();packet(d,src,'DARK',1000,9);packet(d,src,'FIRE',1000,12)
    effect(d,src,{'op':'modify_resource','target':2,'resource':'sp','value':18},5)
    effect(d,src,{'op':'modify_resource','target':2,'resource':'sp','delta':5,'parameters':{'respect_recovery_freeze':True}},15)
    t['components']['abilities'].append('ability/peer/test_skill')
    d['definitions'].append({'id':'ability/peer/test_skill','kind':'ability','activation':{'mode':'manual','costs':[{'resource':'sp','amount':1}]},'timeline':[{'at':0,'effect':{'op':'emit','event':'peer.skill.accepted','target':'source','payload':{}}}]})
    for tick in (11,461):d['scenarioDraft']['commands'].append({'at':tick,'action':'skill','source':'receiver','ability':'ability/peer/test_skill'})
    s=make(finish(d,t),'dark');initial=hp(s);res=10;s.advance(40)
    assert sp(s)==16 and hp(s)==initial-180 and state(s)['remaining']['FIRE']==1000
    assert set(s.ctx.spatial.selection_state('receiver',DEFAULT_STATE)['abnormal_flags'])>={1,24}
    assert any(e['time']==11 for e in events(s,'command.rejected')) and any(e['time']==15 for e in events(s,'resource.recovery_suppressed'))
    s=cpp(s,40,463,'dark');damage=[e for e in events(s,'damage.accepted') if e['payload'].get('source_policy')=='none']
    assert len(damage)==15 and [e['time'] for e in damage]==[9+30*i for i in range(15)]
    assert hp(s)==initial-15*100*(1-res/100) and sp(s)==2 and events(s,'peer.skill.accepted')[0]['time']==461
    assert all(e['payload']['source'] is None and e['payload']['ignore_for_sp'] is True for e in damage)
    assert state(s)['break'] is None and state(s)['remaining']=={'FIRE':1000,'DARK':1000}
    FACTS['dark']={'HP':hp(s),'SP':sp(s),'damage_ticks':[e['time'] for e in damage],'state':state(s),'all_source_none':True}
def normal_attack():
    d,t,src,by=package(isolate=False)
    by['ability/liskam_s1']['activation']['condition']='False'
    packet(d,src,'DARK',1000,9);s=make(finish(d,t),'normal');s=cpp(s,10,100,'normal')
    attacks=[e for e in events(s,'damage.accepted') if e['payload'].get('source')==2]
    assert attacks and all(e['payload']['ability']=='ability/char_107_liskam/normal_attack' for e in attacks)
    assert any(e['time']>9 for e in attacks)
    FACTS['normal_attack']={'attack_ticks':[e['time'] for e in attacks]}
def flags():
    facts=[]
    for flag,immune,expected in [(21,False,1000),(5,False,1000),(21,True,887)]:
        d,t,src,_=package();t['components']['selection_state']['abnormal_flags']=[flag]
        if immune:t['components']['selection_state']['abnormal_immunes']=[flag]
        packet(d,src,'DARK',113,9);s=cpp(make(finish(d,t),'flag'),10,15,'flag')
        assert state(s)['remaining']['DARK']==expected;facts.append({'flag':flag,'immune':immune,'remaining':expected})
    # Mount intentionally skips non-ally rows; an explicitly copied receiver
    # on a neutral test copy exercises eligibility independently of that skip.
    d,t,src,_=package();t['components']['selection_state']['side']=2
    t['components']['elemental']=copy.deepcopy(module()['receiver_template'])
    data=module();d['definitions'].extend(data['rules']+data['buffs']);packet(d,src,'DARK',113,9)
    s=cpp(make(d,'neutral'),10,15,'neutral');assert state(s)['remaining']['DARK']==1000
    FACTS['flags']=facts
def night_layers():
    d,t,src,by=package()
    # Apply the real roster aura member definitions as publicly declared
    # controls; test the modifier composition independently of aura selection.
    effect(d,src,{'op':'apply_buff','target':2,'buff':'buff/support_night_res'},3)
    effect(d,src,{'op':'apply_buff','target':2,'buff':'buff/support_cgbird_skill_res'},4)
    packet(d,src,'FIRE',1000,9);finish(d,t);s=make(d,'night');base=s.ctx.attributes.value('receiver','mres')
    s.advance(8);pre=s.ctx.attributes.value('receiver','mres');s.advance(2);post=s.ctx.attributes.value('receiver','mres')
    assert pre==(base+15)*2.5 and post==(base+15-20)*2.5
    FACTS['night_layers']={'base':base,'before_fire':pre,'after_fire':post,'expected_ADDITION_then_MULTIPLIER':(base+15-20)*2.5,
      'raw_fire_formulaItem':'ADDITION','raw_roster_S3_layer':'direct_ratio','raw_roster_S3_value':1.5,
      'formula_reference':'https://prts.wiki/w/游戏数据基础','HP':hp(s),'SP':sp(s)}
    cpp(make(d,'night_proof'),10,15,'night')
def lifecycle():
    facts=[]
    for key,e in [('dead',{'op':'modify_resource','target':2,'resource':'hp','value':0}),('withdraw',{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}})]:
        d,t,src,_=package();packet(d,src,'DARK',1000,9);effect(d,src,e,20);s=cpp(make(finish(d,t),key),19,80,key)
        assert not s.ctx.active('receiver') and state(s)['break'] is None
        damage=[e for e in events(s,'damage.accepted') if e['payload'].get('source_policy')=='none'];assert len(damage)==1
        facts.append({'kind':key,'state':state(s),'pulses':len(damage)})
    FACTS['lifecycle']=facts
def checkpoint_tamper():
    d,t,src,_=package();packet(d,src,'DARK',1000,9);s=make(finish(d,t),'tamper');s.advance(10)
    cp=write_checkpoint(s,LOG/'tamper.checkpoint.json');c=thaw(load_checkpoint(cp));attempts=[]
    for field in ('remaining','due','generation','task','seq','provenance'):
        altered=copy.deepcopy(c);actor=next(e for e in altered['kernel']['world']['entities'] if e['id']==2);st=actor['components']['runtime']['elemental']
        if field=='remaining':st['remaining']['DARK']=999
        elif field=='provenance':st['break']['provenance']['request']['raw_amount']=1
        else:st['break'][field]+=1
        try:Engine.restore(s.program,altered,providers=providers())
        except (ValueError,KeyError,TypeError) as error:attempts.append({'field':field,'rejected':True,'error':str(error)})
        else:attempts.append({'field':field,'rejected':False})
    FACTS['single_field_in_memory_restore']=attempts
    # Disk bytes are separately bound by the checkpoint hash and reference.
    path=Path(cp['path']);raw=path.read_bytes();changed=raw.replace(b'"DARK":0',b'"DARK":1',1)
    if changed==raw:changed=raw+b' '
    path.write_bytes(changed)
    try:load_checkpoint(cp)
    except ValueError:FACTS['disk_byte_tamper_rejected']=True
    else:raise AssertionError('Bound disk-byte tamper accepted')
    return {'in_memory_accepted':[a['field'] for a in attempts if not a['rejected']]}
def main():
    guards={str(p):sha(p) for p in (SOURCE,TABLE,ROSTER,ROOT/'tools/campaign_elemental_receivers_v1/build.py')};core=implementation_digest()
    for name,fn in [('public_fixed_roster_113',basic),('FIRE1200_RES_before_NoSource',fire),('DARK15pulses_SP_stop_skill24_lock_reset',dark),
      ('normal_attack_continues',normal_attack),('native21_vs5_immunes_neutral',flags),('FIRE_NightS3_layer_composition',night_layers),
      ('death_withdraw_cancel',lifecycle),('checkpoint_single_field_tamper_boundary',checkpoint_tamper)]:
        try:detail=fn();ROWS.append({'case':name,'passed':True,'details':detail})
        except Exception as e:ROWS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
        finally:print(json.dumps(ROWS[-1]),flush=True);gc.collect()
    r={'schema':'ark-sim/elemental-receiver-independent-peer/v1','mechanism_cases_passed':all(x['passed'] for x in ROWS),'implementation':core,
      'primary_unchanged':implementation_digest()==core,'source_hashes':guards,'source_unchanged':all(sha(p)==v for p,v in guards.items()),
      'cases':ROWS,'facts':FACTS,'actual_CP_head_proofs':PROOFS,'peer_source_sha256':sha(__file__),
      'review_scope':'fixed roster FIRE/DARK content mount only; no whole stage or client method body claim',
      'remaining_review':['redeployment reset','prior SP freeze and already active original skill','all15 roster/summon mount scope'],
      'pinned_reference_access':'oldid430495 unavailable via web tool; original raw BSON independently inspected; live PRTS formula cited separately'}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return 0 if r['mechanism_cases_passed'] and r['primary_unchanged'] and r['source_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
