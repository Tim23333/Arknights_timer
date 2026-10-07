"""Short actual public external ACK/deploy and full disk continuation proof."""
import copy,hashlib,json,os,sys,traceback,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
from tools.control_driver.public_ack_v2 import PublicAckDriver
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter0_stage_assembly_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def events(s,k):return [thaw(e) for e in s.session.events if e['type']==k]
def main():
    cases=[];guards={str(p):sha(p) for p in (ROOT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')};core=implementation_digest()
    for stage in ('level_main_00-10','level_main_00-11'):
        try:
            path=ROOT/'packages/campaign/chapter0_stage_models'/(stage+'.source.v2.json');cmdpath=path.with_name(stage+'.public.plan.v4.json');raw=json.loads(path.read_bytes());plan=json.loads(cmdpath.read_bytes());guards[str(path)]=sha(path);guards[str(cmdpath)]=sha(cmdpath);guards[plan['ACK_driver']['path']]=plan['ACK_driver']['sha256']
            p=copy.deepcopy(raw);p['scenarioDraft']['commands']=copy.deepcopy(plan['commands']);first=next(c for c in plan['commands'] if c['action']=='deploy');reject=copy.deepcopy(first);reject['at']=2;reject['alias']='blocked-input-probe';p['scenarioDraft']['commands'].insert(0,reject)
            program=Compiler().compile(p);a=Engine.create(program,event_journal_path=LOG/(stage+'.active.jsonl'));driver=PublicAckDriver(a);driver.advance_to(4);state=a.ctx.state();control=state['controls']['instances']['control/1'];assert control['phase']=='awaiting_ack' and control['waiting_step']==4 and state['input_locks']
            driver_cp=driver.checkpoint();dpath=LOG/(stage+'.driver.checkpoint.json');dpath.write_text(json.dumps(driver_cp)+'\n',encoding='utf8');driver_pin=sha(dpath)
            cp=write_checkpoint(a,LOG/(stage+'.checkpoint.json'));b=Engine.restore(program,load_checkpoint(cp));bd=PublicAckDriver(b,json.loads(dpath.read_bytes()));assert thaw(a.checkpoint())==thaw(b.checkpoint());driver.advance_to(180);bd.advance_to(180);assert driver.checkpoint()==bd.checkpoint();h=replay(program,a.export_replay(),event_journal_path=LOG/(stage+'.head.active.jsonl'));hd=PublicAckDriver(h,driver.checkpoint());assert hd.checkpoint()==driver.checkpoint()
            obs=[observations(s,LOG/(stage+'.'+key+'.events.jsonl')) for s,key in [(a,'forward'),(b,'CP'),(h,'head')]];keys=('snapshot','events','event_count','continuation_state');equal=all(all(v[k]==obs[0][k] for k in keys) for v in obs[1:]);checkpoints=[thaw(s.checkpoint()) for s in (a,b,h)];assert equal and checkpoints[0]==checkpoints[1]==checkpoints[2]
            acknowledges=events(a,'control.acknowledged');story=[e for e in acknowledges if e['payload']['control']=='control/1'];assert len(story)==(3 if stage.endswith('10') else 2) and all(e['payload']['automatic'] is False for e in story)
            c=a.ctx.state()['controls']['instances']['control/1'];assert c['status']=='completed' and not a.ctx.state()['input_locks'];completed=next(e for e in events(a,'control.completed') if e['payload']['control']=='control/1');assert completed['time']==(15 if stage.endswith('10') else 13)
            assert events(a,'command.rejected') and any(e['payload'].get('action',{}).get('alias')==first['alias'] for e in events(a,'command.accepted'))
            actor=a.ctx.entity(first['alias']);assert actor['definition_id']==first['entity'] and a.ctx.active(first['alias']);assert a.ctx.resources.current('system/battle','life')==99999 and a.ctx.state()['pending_waves']>=0
            born=events(a,'entity.created');assert any(e['payload'].get('definition','').startswith('unit/ch0/') for e in born)
            positions=events(a,'spawn.position_resolved');assert positions
            actions=[x['spawn'] for w in p['scenarioDraft']['timeline']['waves'] for f in w['fragments'] for x in f['actions'] if x['kind']=='spawn']
            for event in positions:
                data=event['payload'];samples={x['axis']:x['value'] for x in data['samples']};candidates=[x for x in actions if x['definition']==data['definition'] and x['position']==data['anchor']]
                assert any(all(data['position'][axis]==x['position'][axis]+x['placement']['offset'][axis]+((2*samples[axis]-1)*x['placement']['random_range'][axis]*(-1 if axis=='row' else 1) if axis in samples else 0) for axis in ('row','col')) for x in candidates)
            cases.append({'stage':stage,'passed':True,'source_package_sha256':sha(path),'test_command_changes':'One public rejected deployment during owned story lock; original finite external ACK/deploy commands otherwise unchanged','end':180,'checkpoint_sha256':cp['sha256'],'event_reference':cp['event_reference'],'four_observations_equal':equal,'full_checkpoint_equal':True,'full_checkpoint_digests':[digest(v) for v in checkpoints],
              'observations':[{k:v[k] for k in keys} for v in obs],'driver_checkpoint_sha256':driver_pin,'driver_final':driver.checkpoint(),'driver_CP_head_equal':True,'public_command_ledger':a.export_replay()['commands'],'story_ACKs':story,'story_completed_tick':completed['time'],'command_rejected':events(a,'command.rejected'),'command_accepted':events(a,'command.accepted'),'actual_actor_HP':a.ctx.resources.current(first['alias'],'hp'),'actual_actor_SP':a.ctx.resources.current(first['alias'],'sp'),'DP':a.ctx.resources.current('system/battle','dp'),'base':99999,'actual_spawn_events':born,'spawn_positions_reference_exact':positions,'RNG':thaw(a.session.random.snapshot()),'native_UI_timing_claim':False})
        except Exception as e:cases.append({'stage':stage,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
        print(json.dumps({'stage':stage,'passed':cases[-1]['passed']}),flush=True);gc.collect()
    result={'schema':'ark-sim/chapter0-public-short-prefix/v1','core':core,'passed':all(c['passed'] for c in cases),'cases':cases,'source_guards':guards,'source_unchanged':all(sha(k)==h for k,h in guards.items()),'whole_stage':False,'independent_admission':False,'native_UI_timing_verified':False,'loaded_kernel_module_paths':{k:v.__file__ for k,v in sys.modules.items() if k=='ark_sim' or k.startswith('ark_sim.') if getattr(v,'__file__',None)}}
    (OUT/'prefix.actual.v4.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return 0 if result['passed'] and result['source_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
