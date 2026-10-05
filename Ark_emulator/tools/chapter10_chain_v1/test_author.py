"""Actual public chain impacts, disk CP/head and hostile restore/callback probes."""
import copy, gc, hashlib, json, os, sys, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=(ROOT/'../unpack_work/campaign_c10_chain_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw, digest
from ark_sim.tools.replay import replay
from tools.chapter10_chain_v1.fixture import package
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter10_chain_v1/author.v1.json'
ROWS=[];PROOFS=[];OBS_COUNT=0

def create(name,change=None):
    data=package()
    if change:change(data)
    program=Compiler().compile(data)
    sim=Engine.create(program,seed=17,event_journal_path=LOG/(name+'.active.jsonl'))
    sim.submit({'action':'skill','source':'source','ability':'ability/chain/probe'},at=1)
    return sim

def identity(sim):
    global OBS_COUNT
    path=LOG/('observed_'+str(OBS_COUNT)+'.events.jsonl');OBS_COUNT+=1
    return observations(sim,path)

def proof(sim,at=43,end=100):
    sim.session.advance(at)
    cp=write_checkpoint(sim,LOG/('cp_'+str(len(ROWS))+'.checkpoint.json'))
    loaded=load_checkpoint(cp)
    restored=Engine.restore(sim.program,loaded)
    sim.session.advance(end-at);restored.session.advance(end-at)
    a=identity(sim);b=identity(restored)
    equal=lambda x,y:all(x[k]==y[k] for k in ('snapshot','events','event_count','continuation_state'))
    assert equal(a,b),'Full actual disk CP continuation differs'
    head=replay(sim.program,sim.export_replay(),event_journal_path=LOG/('head_'+str(len(ROWS))+'.active.jsonl'))
    c=identity(head);assert equal(a,c),'Full actual head differs'
    PROOFS.append({'checkpoint_sha256':cp['sha256'],'checkpoint_event_reference':cp['event_reference'],
                  'observations':{k:a[k] for k in ('snapshot','events','event_count','continuation_state')},
                  'actual_CP_equal':True,'actual_head_equal':True})
    return sim

def outcome(sim,kind):return [thaw(e) for e in sim.session.events if e['type']==kind]

def case(name,fn):
    try:fn();ROWS.append({'case':name,'passed':True})
    except Exception as e:ROWS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    finally:gc.collect()

def base():
    s=proof(create('four'))
    expected=[550*.85**i for i in range(4)]
    assert [s.ctx.resources.current('target'+str(i),'hp') for i in range(4)]==[10000-a for a in expected]
    assert s.ctx.resources.current('target4','hp')==10000
    for i,amount in enumerate(expected):assert s.ctx.get('target'+str(i),('runtime','elemental','remaining','DARK'))==10000-amount*.3
    hits=outcome(s,'projectile.hit');assert len(hits)==4 and len({x['payload']['target'] for x in hits})==4
    assert len(outcome(s,'projectile.launched'))==1
    assert [x['time'] for x in hits]==sorted(set(x['time'] for x in hits))
    launched=outcome(s,'projectile.launched')[0];assert launched['time']==38

def controller(data,ability):
    d=copy.deepcopy(data['entities'][0]);d['id']='unit/chain/controller';d['tags']=['observer'];d['components']['selection_state']['side']=2;d['components']['abilities']=[ability];data['entities'].append(d)
    data['scenarioDraft']['initialEntities'].append({'definition':d['id'],'instanceAlias':'controller','position':{'row':4,'col':0}})

def dynamic(name,change_at,change):
    # The change is queued as an actual public manual ability after the first
    # impact; public input replay retains its exact order and submission time.
    def patch(data):
        target=next(x for x in data['entities'] if x['id']=='unit/chain/target')
        for i in range(5):
            d=copy.deepcopy(target);d['id']='unit/chain/target'+str(i);d['tags'].append('target'+str(i));data['entities'].append(d)
            data['scenarioDraft']['initialEntities'][i+1]['definition']=d['id']
        data['selectors'].append({'id':'selector/chain/change','kind':'selector','region':{'type':'all'},'filters':[{'tag':'target1'}],'limit':1})
        data['abilities'].append({'id':'ability/chain/change','kind':'ability','activation':{'mode':'manual'},'selector':'selector/chain/change','duration_seconds':0,'timeline':[{'at':0,'effect':change}]})
        controller(data,'ability/chain/change')
    s=create(name,patch);s.submit({'action':'skill','source':'controller','ability':'ability/chain/change'},at=change_at)
    return proof(s,at=39)

def move():
    s=dynamic('move',39,{'op':'move','position':{'row':4,'col':9}})
    assert s.ctx.resources.current('target1','hp')==10000
    assert len(outcome(s,'projectile.hit'))==1

def death():
    s=dynamic('death',41,{'op':'damage','damage_type':'true','scale':100})
    assert not s.ctx.alive('target1')
    assert s.ctx.get('target1',('runtime','elemental','remaining','DARK'))==10000
    assert len(outcome(s,'projectile.hit'))==1

def dead_first_no_EP():
    def patch(d):
        d['entities'][1]['components']['resources']['hp']['initial']=100
    s=proof(create('deadfirst',patch),at=38)
    assert not s.ctx.alive('target0')
    assert s.ctx.get('target0',('runtime','elemental','remaining','DARK'))==10000
    assert len(outcome(s,'projectile.hit'))==4

def current_flags():
    def patch(data):
        t=copy.deepcopy(data['entities'][1]);t['id']='unit/chain/free';t['components']['selection_state']['target_free']=True;data['entities'].append(t)
        data['scenarioDraft']['initialEntities'][2]['definition']=t['id']
    s=proof(create('free',patch),at=38)
    assert s.ctx.resources.current('target1','hp')==10000
    assert len(outcome(s,'projectile.hit'))==1
    assert any(x['payload']['reason']=='target_free' for x in outcome(s,'projectile.chain.candidate.rejected'))

def source_retirement(policy):
    def patch(data):
        data['projectiles'][0]['lifecycle']['source_invalid']=policy
        data['selectors'].append({'id':'selector/chain/self','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
        data['abilities'].append({'id':'ability/chain/retire','kind':'ability','activation':{'mode':'manual'},'selector':'selector/chain/self','duration_seconds':0,'timeline':[{'at':0,'effect':{'op':'retire','parameters':{'reason':'withdrawn'}}}]})
        controller(data,'ability/chain/retire')
    s=create('source_'+policy,patch);s.submit({'action':'skill','source':'controller','ability':'ability/chain/retire'},at=41);s=proof(s,at=39)
    assert not s.ctx.active('source')
    assert len(outcome(s,'projectile.hit'))==(4 if policy=='retain' else 1)

def reject_tamper():
    s=create('tamper');s.session.advance(43);cp=s.checkpoint()
    base=thaw(cp)
    # Each forged checkpoint changes one ownership-relevant value while the
    # actual event lineage remains untouched.
    for key in ('position','scale','visited','source_snapshot','task'):
        c=copy.deepcopy(base)
        entity=next(e for e in c['kernel']['world']['entities'] if e['definition_id']=='system/battle')
        x=entity['components']['projectiles']['instances']['projectile/1']
        if key=='position':x['position']['col']+=.1
        elif key=='scale':x['effect']['health_effect']['scale']=99
        elif key=='visited':x['chain']['visited'].append(999)
        elif key=='source_snapshot':x['chain']['launch_source']['components']['attributes']['base']['atk']=99999
        else:
            job=x['chain']['step_task']['task'];next(t for t in c['kernel']['scheduler']['tasks'] if t['id']==job['id'])['at']+=1
        try:Engine.restore(s.program,c)
        except (ValueError,KeyError):pass
        else:raise AssertionError('Restored forged '+key+' accepted')

def reject_callbacks():
    s=create('callbacks');s.session.advance(43);before=s.checkpoint();x=s.ctx.projectiles._get('projectile/1')
    for callback,payload in [(s.ctx.projectiles.step,{'projectile':'projectile/1'}),
                             (s.ctx.projectiles.chains.next,{'projectile':'projectile/1','hop':x['chain']['hop'],'hit_event':0})]:
        try:callback(s.session,payload)
        except ValueError:pass
        else:raise AssertionError('Unowned callback accepted')
        assert s.checkpoint()==before,'Rejected callback mutated full state'

def main():
    core=implementation_digest()
    for name,fn in [('public_four_actual_health_EP',base),('current_move_outside_radius',move),
                    ('current_target_death',death),('health_death_before_EP',dead_first_no_EP),
                    ('current_target_free_rejected',current_flags),('source_invalid_retain',lambda:source_retirement('retain')),
                    ('source_invalid_cancel',lambda:source_retirement('cancel')),('restore_tamper_rejected',reject_tamper),
                    ('unowned_callbacks_rejected_atomic',reject_callbacks)]:case(name,fn)
    result={'schema':'ark-sim/finite-chain-author/v1','passed':all(x['passed'] for x in ROWS),
            'implementation':core,'identity_stable':implementation_digest()==core,'actual_cases':ROWS,
            'actual_CP_head_proofs':PROOFS,'actual_game_accuracy_verified':False,'primary_modified':False}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':result['passed'],'rows':ROWS,'proof_count':len(PROOFS)}),flush=True)
    return 0 if result['passed'] and result['identity_stable'] else 1
if __name__=='__main__':raise SystemExit(main())
