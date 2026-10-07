"""Own different-clock pre-finish and same-tick completion reborrow counters."""
import sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_owned_channel_phase_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from tools.campaign_resource_channel_peer_v1.fixtures import package,providers,PROFILE,ABILITY
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_owned_channel_phase_peer_v1';OUT.mkdir(parents=True,exist_ok=True);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def fixture():
    p=package(duration=.41,interval=.13,capacity=83)
    p['definitions'].append({'id':'ruleset/peer/phase17','kind':'ruleset','extends':'ruleset/ark_standard','quantum':1/17})
    a=next(d for d in p['definitions'] if d['id']==ABILITY);a['duration_seconds']=2;a['channel_completion']={'mode':'after_last_owned_channel','post_delay_seconds':.23};a['timeline'][0].pop('at');a['timeline'][0]['at_seconds']=.4
    p['scenarioDraft']['ruleset']='ruleset/peer/phase17';return p
def main():
    core=implementation_digest();assert core=='e3bca4cc10d3bed87c0f635faa676377afacf97631e38a15ad2d1837389332d2';paths=[Path(__file__),ROOT/'tools/campaign_resource_channel_peer_v1/fixtures.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']];before={str(p):sha(p) for p in paths}
    p=fixture();reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=817);s.advance(10);source=s.session.world.resolve('sender');cast=next(iter(s.ctx.get(source,('runtime','casts')).values()));pre=s.checkpoint();(LOG/'pre.before.checkpoint.json').write_text(json.dumps(pre),encoding='utf8')
    s.ctx.abilities.finish(s.session,{'source':source,'cast':cast['id']});after=s.checkpoint();(LOG/'pre.after.checkpoint.json').write_text(json.dumps(after),encoding='utf8');pre_changed=pre!=after
    s2=Engine.create(program,providers=reg,seed=817);rows=[];original=s2.ctx.attachments.stop
    def borrowed(uid,reason):
        result=original(uid,reason);session=s2.session;x=s2.ctx.attachments.current(uid)
        if x and not x['active'] and not rows:
            cast=thaw(s2.ctx.abilities._active(x['source'],x['cast']));e=next(e for e in reversed(list(session.events)) if e['type']=='attachment.finished' and e['payload']['attachment']==x['id']);before=copy.deepcopy(s2.ctx.get(x['source'],('runtime','casts')));event_count=len(session.events)
            from ark_sim.domains.channel_phases import completed
            completed(s2.ctx.abilities,x['source'],cast,x['id'],e['id'])
            rows.append({'time':session.time,'event':e['id'],'completed_before':before[cast['id']].get('channel_completed_events'),'completed_after':s2.ctx.get(x['source'],('runtime','casts',cast['id'],'channel_completed_events')),'events_before':event_count,'events_after':len(session.events),'changed':before!=s2.ctx.get(x['source'],('runtime','casts'))})
        return result
    s2.ctx.attachments.stop=borrowed;s2.advance(18)
    diagnostic={'pre_changed':pre_changed,'quantum':s2.session.quantum,'reborrow_rows':rows,'attachments':thaw(s2.ctx.attachments.state()),'phase_events':[thaw(e) for e in s2.session.events if e['type'].startswith(('attachment.','ability.channel','ability.finished'))]}
    probe=OUT/'counter.diagnostic.v5.json';assert not probe.exists();probe.write_text(json.dumps(diagnostic,indent=2)+'\n',encoding='utf8')
    assert pre_changed and rows and rows[0]['changed']
    afterguard={str(p):sha(p) for p in paths};assert before==afterguard
    report={'schema':'ark-sim/independent-old-phase-permission-counter/v1','core':core,'source_before':before,'source_after':afterguard,'source_equal':True,'quantum':1/17,'pre_delay_seconds':.4,'post_delay_seconds':.23,'pre_direct_finish_changed_checkpoint':pre_changed,'pre_finish_requested_before':cast.get('finish_requested'),'pre_finish_requested_after':s.ctx.get(source,('runtime','casts',cast['id'],'finish_requested')),'same_tick_reborrow':rows,'permission_passed':False,'actual_counter_observed':True,'program':program.fingerprint,'old_e3_not_promotable':True};path=OUT/'old.e3.counter.v1.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'counter_observed':True,'source_equal':True}));return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        file=OUT/'counter.development.error.v5.json';assert not file.exists();file.write_text(json.dumps({'error':str(error),'traceback':traceback.format_exc(),'counter_not_completed':True},indent=2)+'\n',encoding='utf8');raise
