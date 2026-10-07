"""NativeFlame -> original fixed Liskam HP/FIRE/SP, distinct fresh scene."""
import sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_elemental_lease_v4_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter09_elemental_successor_v1.providers import providers
FIRE='ability/ch9/duspfr/flame';SENDER='unit/ch9/duspfr/body';RECIPIENT='unit/char_107_liskam';LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter09_elemental_successor_peer_v1';FACT={};sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def fixture(stage,cancel=False,distance=.8):
    path=ROOT/f'packages/campaign/chapter09_stage_models/level_main_{stage}.elemental_successor.v1.life99999.finite_run_v1.json';p=json.loads(path.read_bytes());original={d['id']:copy.deepcopy(d) for d in p['definitions']};defs={d['id']:d for d in p['definitions']};owned={a for id in [SENDER,RECIPIENT] for a in defs[id]['components']['abilities']};changed=[]
    for id in owned:
        d=defs[id];a=d.get('activation',{})
        if id!=FIRE and (a.get('mode')=='automatic_attack' or a.get('parameters',{}).get('auto_when_ready')):a['condition']='False';changed.append(id)
    p['definitions'].append({'id':'buff/peer/fire_silence','kind':'buff','selection_flags':{'abnormal_flags':[12]}})
    for rule in p['definitions']:
        if rule['id']=='rule/campaign/elemental_receivers/eligible':rule['parameters']['buff_flags']['buff/peer/fire_silence']={'flags':[12],'immunes':[]}
    scene={'id':'scene/peer/native_fire/'+stage+('/cancel' if cancel else '/normal'),'ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'initialEntities':[{'definition':SENDER,'instanceAlias':'enemy','position':{'row':1,'col':1}},{'definition':RECIPIENT,'instanceAlias':'operator','position':{'row':1,'col':1+distance},'deployed':True}],'resources':{'dp':{'initial':10,'capacity':99},'life':{'initial':99999,'capacity':99999}},'commands':[]}
    if cancel:scene['scheduledEffects']=[{'at':40,'effect':{'op':'apply_buff','target':2,'buff':'buff/peer/fire_silence'}}]
    p['scenarioDraft']=scene;assert original[SENDER]['components']['attributes']==defs[SENDER]['components']['attributes'] and original[RECIPIENT]['components']['attributes']==defs[RECIPIENT]['components']['attributes'] and original[SENDER]['components']['abilities']==defs[SENDER]['components']['abilities'] and original[RECIPIENT]['components']['abilities']==defs[RECIPIENT]['components']['abilities']
    return p,path,{'auto_isolation_conditions_only':changed,'all_owned_ability_declarations_preserved':True,'actor_HP_stats_unchanged':True}
def run(stage,cancel=False,distance=.8):
    p,source,isolation=fixture(stage,cancel,distance);reg=providers(stage);program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=9916);s.advance(17);path=LOG/(stage+('_cancel' if cancel else '')+'.checkpoint.json');path.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(program,json.loads(path.read_bytes()),providers=reg);s.advance(39);r.advance(39);h=replay(program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==h.checkpoint()
    events=[thaw(e) for e in s.session.events if e['type'] in ['ability.started','attachment.started','attachment.reached','attachment.finished','damage.accepted','elemental.loss.accepted','resource.changed']]
    hits=[e for e in events if e['type']=='damage.accepted' and e['payload']['target']==s.session.world.resolve('operator')];loss=[e for e in events if e['type']=='elemental.loss.accepted'];attached=list(s.ctx.attachments.state()['instances'].values());hp=s.ctx.resources.current('operator','hp');ep=s.ctx.get('operator',('runtime','elemental','remaining','FIRE'));sp=s.ctx.resources.current('operator','sp')
    key=stage+('/outside_trigger' if distance>1 else '/cancel' if cancel else '/normal');FACT[key]={'source_sha256':sha(source),'isolation':isolation,'events':events,'HP':hp,'FIRE':ep,'SP':sp,'attachment_state':thaw(attached),'checkpoint_sha256':sha(path),'program_fingerprint':program.fingerprint,'runtime_fingerprint':s.runtime_fingerprint,'full_CPP_head':True}
    if distance>1:
        assert not attached and not hits and ep==1000;return
    expected=2 if cancel else 3
    assert len(hits)==expected and all(e['payload']['amount']==54 for e in hits)
    assert hp==3124-54*expected and ep==1000-30*expected and len(loss)==expected
    assert all(hits[i+1]['time']-hits[i]['time']==15 for i in range(len(hits)-1))
    assert s.ctx.resources.current('enemy','hp')==8000 and len(s.ctx.get('enemy',('abilities',)))==7
    # This oracle follows the two original M26 declarations (event recovery and
    # talent own+1). It does not certify native/client duplication correctness.
    assert sp==2*expected
    FACT[key]['SP_scope']='Original frozen M26 source-model event recovery + talent self+1 both preserved; native duplicate-attribution accuracy remains separately pending.'
    if cancel:assert not attached[0]['active'] and attached[0]['packets']==2
def main():
    assert implementation_digest()=='94d2f5cfcc42f8845c6cb23643f1910aa94a78115a60d83813d0738df6db8c63'
    files=[Path(__file__),ROOT/'tools/chapter09_elemental_successor_v1/providers.py',ROOT/'tools/campaign_elemental_receivers_v1/build.py',ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.elemental_successor.v1.life99999.finite_run_v1.json']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']];before={str(p):sha(p) for p in files};results=[]
    for stage,cancel,distance in [('09-16',False,.8),('09-16',True,.8),('09-16',False,1.05)]:
        try:run(stage,cancel,distance);results.append({'stage':stage,'cancel':cancel,'distance':distance,'passed':True})
        except Exception as e:results.append({'stage':stage,'cancel':cancel,'distance':distance,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    after={str(p):sha(p) for p in files};code=0 if all(r['passed'] for r in results) and before==after else 1
    path=OUT/'native.fire.actual.v2.json';assert not path.exists();path.write_text(json.dumps({'core':implementation_digest(),'source_before':before,'source_after':after,'source_equal':before==after,'actual_exit':code,'results':results,'facts':FACT,'whole_stage_approved':False,'client_verified':False,'919_has_no_native_flame_actor':True},indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
