"""Independent public-command scenes for frozen finite chains. No author assertions."""
import copy, gc, hashlib, json, os, subprocess, sys, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=(ROOT/'../unpack_work/campaign_c10_chain_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.chapter10_chain_v1.native_module import build_fragment
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter10_chain_peer_v1/result.v1.json'
ROWS=[];PROOFS=[];SERIAL=0
EXPECTED='09c265c4a5f8d849f20d08a0e073db558d8d6a727f1060f3ad2a63cec2e1f7c6'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def scene(native=False):
    # Only consume the expressly exported native source fragment. All entity,
    # spatial, receiver, command and oracle construction is independently owned.
    fragment,provenance=build_fragment();d=copy.deepcopy(fragment)
    d.update(schemaVersion=2,entities=[],buffs=[])
    def unit(key,tags,side,atk=0,mres=20):
        return {'id':'unit/peer/'+key,'kind':'entity','tags':tags,'components':{
          'attributes':{'base':{'max_hp':20000,'atk':atk,'def':37,'mres':mres,'attack_interval':4,'attack_speed_ratio':1}},
          'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},
          'selection_state':{'side':side,'category':1,'motion':1},'spatial':{},
          'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    a=d['abilities'][0]
    if not native:a.update(activation={'mode':'manual'},duration_seconds=8/30,timeline=[{'at':7,'effect':a['timeline'][0]['effect']}])
    source=unit('attacker',['enemy','attacker'],1,550 if native else 880,0)
    source['components']['abilities']=[a['id']];d['entities'].append(source)
    ep_rules={r['contract']:r['id'] for r in d['rules'] if r['contract'].startswith('elemental.')}
    profile={'capacity':20000,'resistance':0,'recovery_rate':0,'break_duration_seconds':1,
       'rules':{k:v for k,v in ep_rules.items() if k!='elemental.eligibility' and k!='elemental.packet'},'on_break':[],'on_end':[]}
    initials=[{'definition':source['id'],'instanceAlias':'attacker','position':{'row':4,'col':2}}]
    for i in range(6):
        t=unit('receiver'+str(i),['player','receiver'+str(i)],0,mres=0 if native else 20)
        t['components']['elemental']={'eligibility_rule':ep_rules['elemental.eligibility'],'elements':{'DARK':copy.deepcopy(profile)}}
        d['entities'].append(t);initials.append({'definition':t['id'],'instanceAlias':'r'+str(i),'position':{'row':4,'col':3.3+1.2*i}})
    controls={
      'atk':{'op':'apply_buff','target':2,'buff':'buff/peer/atk'},
      'res':{'op':'apply_buff','target':3,'buff':'buff/peer/res'},
      'move':{'op':'move','target':4,'position':{'row':0,'col':11}},
      'dead':{'op':'modify_resource','target':4,'resource':'hp','value':0},
      'free':{'op':'apply_buff','target':4,'buff':'buff/peer/free'},
      'withdraw':{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}}
    d['buffs']=[{'id':'buff/peer/'+key,'kind':'buff','duration_seconds':8,**value} for key,value in
      [('atk',{'modifiers':[{'attribute':'atk','layer':'flat','value':120}]}),
       ('res',{'modifiers':[{'attribute':'mres','layer':'flat','value':30}]}),
       ('free',{'selection_flags':{'target_free':True}})]]
    ctrl=unit('controller',['observer'],2,0,0);ctrl['components']['abilities']=[]
    for k,e in controls.items():
        aid='ability/peer/'+k;ctrl['components']['abilities'].append(aid)
        d['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual','on_start':[e]},'timeline':[]})
    d['entities'].append(ctrl);initials.append({'definition':ctrl['id'],'instanceAlias':'controller','position':{'row':0,'col':0}})
    d['scenarioDraft']={'id':'scene/peer/chain/'+('native' if native else 'parameterized'),'ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':13},'initialEntities':initials}
    return d,provenance
def make(name,patch=None,native=False):
    global SERIAL
    SERIAL+=1;d,p=scene(native)
    if patch:patch(d)
    s=Engine.create(Compiler().compile(d),seed=71231,event_journal_path=LOG/(str(SERIAL)+'_'+name+'.active.jsonl'))
    if not native:s.submit({'action':'skill','source':'attacker','ability':d['abilities'][0]['id']},at=1)
    return s
def command(s,key,at):s.submit({'action':'skill','source':'controller','ability':'ability/peer/'+key},at=at)
def events(s,kind):return [thaw(e) for e in s.session.events if e['type']==kind]
def identity(s,label):return observations(s,LOG/(str(SERIAL)+'_'+label+'.events.jsonl'))
def proof(s,cut=12,end=70):
    s.session.advance(cut-s.session.time)
    cp=write_checkpoint(s,LOG/(str(SERIAL)+'.checkpoint.json'))
    loaded=load_checkpoint(cp);r=Engine.restore(s.program,loaded)
    s.session.advance(end-s.session.time);r.session.advance(end-r.session.time)
    h=replay(s.program,s.export_replay(),event_journal_path=LOG/(str(SERIAL)+'.head.active.jsonl'))
    obs=[identity(x,label) for x,label in [(s,'forward'),(r,'cp'),(h,'head')]]
    keys=('snapshot','events','event_count','continuation_state')
    assert all(all(o[k]==obs[0][k] for k in keys) for o in obs[1:]),'Full disk CP/head observations diverged'
    PROOFS.append({'cut':cut,'end':end,'checkpoint_sha256':cp['sha256'],'event_reference':cp['event_reference'],
      'observations':[{k:o[k] for k in keys} for o in obs],'actual_disk_CP_equal':True,'actual_head_equal':True})
    return s
def check_amount(s,i,amount,ep):
    assert abs(s.ctx.resources.current('r'+str(i),'hp')-(20000-amount))<1e-9
    assert abs(s.ctx.get('r'+str(i),('runtime','elemental','remaining','DARK'))-(20000-ep))<1e-9
def four():
    s=make('four');s.session.advance(12)
    x=s.ctx.projectiles._get('projectile/1');assert x['state']=='active' and x['waiting_cast']
    assert s.ctx.get('attacker',('runtime','casts')),'Cast ended before complete projectile'
    s=proof(s,12)
    hits=events(s,'projectile.hit');assert len(hits)==4 and len({e['payload']['target'] for e in hits})==4
    assert [e['time'] for e in hits]==sorted(set(e['time'] for e in hits))
    assert len(events(s,'projectile.launched'))==1 and len(events(s,'projectile.invalid'))==1
    for i in range(4):check_amount(s,i,880*.85**i*.8,880*.85**i*.3)
    for i in (4,5):check_amount(s,i,0,0)
    assert not s.ctx.get('attacker',('runtime','casts'))
    selections=events(s,'projectile.chain.selection')
    assert all(e['payload']['selected'] not in e['payload']['excluded'] for e in selections)
def dynamic_attributes():
    s=make('current_attributes');command(s,'atk',9);command(s,'res',10);s=proof(s,10)
    check_amount(s,0,1000*.5,300)
    for i in range(1,4):check_amount(s,i,1000*.85**i*.8,1000*.85**i*.3)
def changed_next(key):
    s=make('current_'+key);command(s,key,12);s=proof(s,11)
    assert len(events(s,'projectile.hit'))==1
    assert s.ctx.get('r1',('runtime','elemental','remaining','DARK'))==20000
    if key=='dead':assert not s.ctx.alive('r1')
    else:assert s.ctx.resources.current('r1','hp')==20000
    if key=='free':assert any(e['payload']['reason']=='target_free' for e in events(s,'projectile.chain.candidate.rejected'))
def killed_by_health():
    def patch(d):d['entities'][1]['components']['resources']['hp']['initial']=100
    s=proof(make('health_kills',patch),10)
    assert not s.ctx.alive('r0') and s.ctx.get('r0',('runtime','elemental','remaining','DARK'))==20000
    assert len(events(s,'projectile.hit'))==4
def dead_inflight():
    s=make('dead_inflight');command(s,'dead',14);s=proof(s,13)
    assert not s.ctx.alive('r1') and s.ctx.get('r1',('runtime','elemental','remaining','DARK'))==20000
    assert len(events(s,'projectile.hit'))==1
def withdrawn(policy):
    def patch(d):d['projectiles'][0]['lifecycle']['source_invalid']=policy
    s=make('withdraw_'+policy,patch);command(s,'atk',9);command(s,'withdraw',12);s=proof(s,11)
    assert not s.ctx.active('attacker')
    assert len(events(s,'projectile.hit'))==(4 if policy=='retain' else 1)
    if policy=='retain':
        # Actual retained source uses the documented cast snapshot fallback.
        for i in range(1,4):check_amount(s,i,880*.85**i*.8,880*.85**i*.3)
def native():
    s=proof(make('native',native=True),40,95)
    assert events(s,'projectile.launched')[0]['time']==37
    assert len(events(s,'projectile.hit'))==4
    for i in range(4):check_amount(s,i,550*.85**i,550*.85**i*.3)
def hostile():
    s=make('hostile');s.session.advance(12);before=thaw(s.checkpoint());x=s.ctx.projectiles._get('projectile/1')
    callbacks=[lambda:s.ctx.projectiles.step(s.session,{'projectile':x['id']}),
      lambda:s.ctx.projectiles.chains.next(s.session,{'projectile':x['id'],'hop':x['chain']['hop'],'hit_event':x['chain']['history'][0]['hit_event']}),
      lambda:s.ctx.projectiles.chains.impact(x,s.ctx.projectiles._definition(x),x['trace_target'],x['chain']['history'][0]['hit_event']),
      lambda:s.ctx.projectiles._hit(x,s.ctx.projectiles._definition(x),x['trace_target'])]
    # Pending can be absent at this boundary; direct callback still must fail.
    for cb in callbacks:
        try:cb()
        except ValueError:pass
        else:raise AssertionError('Unowned task or direct impact accepted')
        assert thaw(s.checkpoint())==before,'Rejection failed full atomic rollback'
    attempts=[]
    for field in ('position','multiplier','visited','base_effect','launch_source','launch_task','history','step_task','expire_task','scheduler','random','cast'):
        c=copy.deepcopy(before);b=next(e for e in c['kernel']['world']['entities'] if e['definition_id']=='system/battle');p=b['components']['projectiles']['instances']['projectile/1'];chain=p['chain']
        if field=='position':p['position']['col']+=.125
        elif field=='multiplier':chain[field]=.01
        elif field=='visited':chain[field].append(77)
        elif field=='base_effect':chain[field]['element_effect']['parameters']['ratio']=9
        elif field=='launch_source':chain[field]['components']['attributes']['base']['atk']=9999
        elif field=='launch_task':chain[field]['at']+=1
        elif field=='history':chain[field][0]['impact']['row']+=1
        elif field in ('step_task','expire_task'):chain[field]['task']['seq']+=1
        elif field=='scheduler':c['kernel']['scheduler']['tasks']=[t for t in c['kernel']['scheduler']['tasks'] if t['id']!=chain['expire_task']['task']['id']]
        elif field=='random':chain['history'][0]['random']['seed']=-999
        else:p['cast']['id']='forged/cast'
        try:Engine.restore(s.program,c)
        except (ValueError,KeyError,TypeError):attempts.append(field)
        else:raise AssertionError('Forged '+field+' restore accepted')
    return attempts
def main():
    frozen=json.loads((ROOT/'validation/campaign/chapter10_chain_v1/frozen.v1.json').read_bytes())
    inventory=json.loads((ROOT/'validation/campaign/chapter10_chain_v1/paused.source.snapshot.v1.json').read_bytes())['source_inventory']
    assert implementation_digest()==EXPECTED
    assert len(frozen['changed_sources'])==5
    for row in frozen['changed_sources']:assert sha(row['candidate'])==row['sha256']
    guards={str(CAND/'ark_sim'/p):v for p,v in inventory.items()}
    assert len(guards)==96 and all(sha(p)==v for p,v in guards.items())
    author_guards=frozen['owned_tool_sources']
    assert all(sha(p)==v for p,v in author_guards.items())
    primary=subprocess.check_output([sys.executable,'-c','from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'],cwd=ROOT,text=True).strip()
    for name,fn in [('four_public_sequential_waiting_no_repeat',four),('source_target_attributes_at_hit',dynamic_attributes),
      ('next_position_at_selection',lambda:changed_next('move')),('next_liveness_at_selection',lambda:changed_next('dead')),
      ('next_eligibility_at_selection',lambda:changed_next('free')),('health_death_prevents_EP',killed_by_health),('target_dies_inflight_no_EP',dead_inflight),
      ('source_withdraw_retained_snapshot',lambda:withdrawn('retain')),('source_withdraw_cancel',lambda:withdrawn('cancel')),
      ('native_fragment_actual_parameters',native),('ownership_restore_and_rollback',hostile)]:
        try:extra=fn();ROWS.append({'case':name,'passed':True,'details':extra})
        except Exception as e:ROWS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
        finally:
            print(json.dumps(ROWS[-1]),flush=True);gc.collect()
    result={'schema':'ark-sim/finite-chain-independent-peer/v1','implementation':EXPECTED,'frozen_sha256':sha(ROOT/'validation/campaign/chapter10_chain_v1/frozen.v1.json'),
      'primary_observed':primary,'primary_frozen':frozen['primary'],'candidate_inventory_count':len(guards),'candidate_unchanged':all(sha(p)==v for p,v in guards.items()),
      'author_tools_unchanged':all(sha(p)==v for p,v in author_guards.items()),'peer_script_sha256':sha(__file__),
      'passed':all(r['passed'] for r in ROWS),'actual_cases':ROWS,'actual_CP_head_proofs':PROOFS,
      'scope':'finite chained projectile and native RangedAttack fragment only; EmptyAbility, behavior, deathrattle and full enemy/stage excluded',
      'full_suite_passed':False,'actual_game_accuracy_verified':False,'formal_approval':False}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':result['passed'],'rows':ROWS,'proofs':len(PROOFS)}),flush=True)
    return 0 if result['passed'] and result['candidate_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
