"""Source coupled consumers: public execution, shared leases, visibility, timing."""
import json,sys,hashlib,traceback,copy,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter09_coupled_v2.build_v2 import build,providers,CORE,OUT,sha,DEFAULT_STATE,implementation_digest
from ark_sim import Compiler,Engine
from ark_sim.contracts import digest
from ark_sim.tools.replay import replay
LOG=Path('E:/ArkSimLogs/runs/chapter09_coupled_author_v2');REPORT=ROOT/'validation/campaign/chapter09_coupled_v2';RESULTS=[];ARTIFACTS=[];CLEANUP=[]
def package(actors,*,profile='native_collider',detect=True,commands=None):
    p=build(radius_profile=profile,partner_detect_invisible=detect);ids={u['metadata']['native_reference']['id'].split('_')[-1]:u['id'] for u in p['entities']}
    p['entities'].append({'id':'unit/coupled_probe/player','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':200000,'atk':10,'def':100,'mres':20,'attack_speed_ratio':1,'block_count':2}},'resources':{'hp':{'initial':200000,'capacity_attribute':'max_hp','role':'health'}},'selection_state':{'side':0,'motion':1,'category':1},'spatial':{},'deployable':{'cost':0}}})
    initial=[]
    for kind,alias,col,options in actors:
        item={'definition':ids[kind] if kind in ids else 'unit/coupled_probe/player','instanceAlias':alias,'position':{'row':1,'col':col}}
        item.update(options);initial.append(item)
    p['scenarioDraft']={'id':'scene/coupled_probe','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':8},'resources':{'dp':{'initial':100,'capacity':1000}},'initialEntities':initial,'commands':commands or []}
    return p
def sim(actors,**kwargs):return Engine.create(Compiler(providers=providers()).compile(package(actors,**kwargs)),providers=providers(),seed=9175)
def actor(kind,alias,col,**kwargs):return kind,alias,col,kwargs
def route(col):return {'startPosition':{'row':1,'col':col},'endPosition':{'row':1,'col':7},'checkpoints':[]}
def state(s,alias):return s.ctx.spatial.selection_state(alias,DEFAULT_STATE)
def stat(s,alias,k):return s.ctx.attributes.value(alias,k)
def refs(s,alias):return s.session.world.resolve(alias)
def cleanup():
    if LOG.exists() and any(LOG.glob('*.json')):
        r=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs_v2.py'),'--run-dir',str(LOG),'--apply','--minimum-age-minutes','0','--completed-pid',str(os.getpid())],capture_output=True,text=True,encoding='utf8',check=True);CLEANUP.append(json.loads(r.stdout))
def case(name,fn):
    try:fn();RESULTS.append({'case':name,'passed':True})
    except Exception as error:RESULTS.append({'case':name,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    finally:cleanup()
def source_and_db_ownership():
    p=build();metadata=p['manifest']['metadata'];assert metadata['unused_db_rows']['enemy_1174_duholy']['rows'][0]['prefabKey']=='Flame'
    assert all(not c for c in [metadata['native_closures'][key]['owned_native_skill_components'] for key in metadata['native_closures']]);assert not any('Flame' in a['id'] for a in p['abilities'])
    try:build(required_skill_policy='all_db_rows')
    except ValueError as error:assert 'no proven owned native component' in str(error)
    else:raise AssertionError('DB-only Flame silently granted')
    for path,pin in metadata['source_locks'].items():assert sha(Path(path))==pin
    for unit in p['entities']:
        name=unit['metadata']['native_reference']['id'];raw=metadata['native_closures'][name]['variant']['native_enemy']['resolved']['attributes'];base=unit['components']['attributes']['base'];assert base['max_hp']==raw['maxHp'] and base['atk']==raw['atk'] and base['def']==raw['def']
def single_pair_stats():
    s=sim([actor('duholy','h',1),actor('dushdo','d',1.5),actor('player','p',1.8)])
    assert abs(stat(s,'d','attack_interval')-.9)<1e-9;assert abs(stat(s,'p','attack_speed_ratio')-.7)<1e-9;assert stat(s,'h','taunt_level')==1
    assert stat(s,'h','mres')==70 and stat(s,'d','mres')==0;assert 9 in state(s,'d')['abnormal_flags']
def radius_profiles():
    for distance,profile,expect in [(1,'native_collider',.7),(1+1e-5,'native_collider',1),(1.05,'trait_blackboard',.7),(1.1001,'trait_blackboard',1)]:
        s=sim([actor('duholy','h',1),actor('dushdo','d',1.5),actor('player','p',1+distance)],profile=profile);assert abs(stat(s,'p','attack_speed_ratio')-expect)<1e-9
    for distance,expect in [(1,.9),(1.0001,2.1)]:
        s=sim([actor('duholy','h',1),actor('dushdo','d',1+distance)]);assert abs(stat(s,'d','attack_interval')-expect)<1e-9
def marker_visibility_profiles():
    s=sim([actor('duholy','h',1),actor('dushdo','d',1.5)],detect=False);assert stat(s,'d','attack_interval')==2.1
    s.ctx.buffs.remove(refs(s,'d'),'buff/ch9/coupled/dushdo/invisible_owner');s.ctx.buffs.reconcile();assert abs(stat(s,'d','attack_interval')-.9)<1e-9
    s=sim([actor('duholy','h',1),actor('dushdo','d',1.5)]);s.ctx.buffs.remove(refs(s,'d'),'buff/ch9/coupled/dushdo/mask');s.ctx.buffs.reconcile();assert stat(s,'d','attack_interval')==2.1
def multiple_sources_last_departure():
    s=sim([actor('duholy','h1',1),actor('duholy','h2',1.1),actor('dushdo','d1',1.5),actor('dushdo','d2',1.6),actor('player','p',1.8)])
    assert abs(stat(s,'p','attack_speed_ratio')-.7)<1e-9 and abs(stat(s,'d1','attack_interval')-.9)<1e-9
    children=[x for x in s.ctx.buffs._instances(refs(s,'p')) if x['definition']=='buff/ch9/coupled/duholy/aspd_down'];assert len(children)==1 and len(children[0]['aura_leases'])==2
    trigger=[x for x in s.ctx.buffs._instances(refs(s,'d1')) if x['definition']=='buff/ch9/coupled/dushdo/trigger'];assert len(trigger)==1 and len(trigger[0]['aura_leases'])==2
    for alias in ('h1','h2'):
        s.submit({'action':'withdraw','source':alias});s.session.advance(1)
        assert not s.ctx.active(refs(s,alias))
        assert abs(stat(s,'p','attack_speed_ratio')-(.7 if alias=='h1' else 1))<1e-9
        assert abs(stat(s,'d1','attack_interval')-(.9 if alias=='h1' else 2.1))<1e-9
    starts=[e for e in s.session.events if e['type']=='coupled.trait.started' and e['payload']['target']==refs(s,'d1')];ends=[e for e in s.session.events if e['type']=='coupled.trait.finished' and e['payload']['target']==refs(s,'d1')];assert len(starts)==len(ends)==1
def silence_and_aura():
    s=sim([actor('duholy','h',1),actor('dushdo','d',1.5),actor('player','p',1.8)]);s.ctx.set(refs(s,'h'),('selection_state','abnormal_flags'),[12]);s.ctx.buffs.applicability.reconcile();assert stat(s,'h','mres')==0 and abs(stat(s,'p','attack_speed_ratio')-.7)<1e-9 and abs(stat(s,'d','attack_interval')-.9)<1e-9
    s.ctx.set(refs(s,'h'),('selection_state','abnormal_flags'),[]);s.ctx.buffs.applicability.reconcile();assert stat(s,'h','mres')==70
def real_block_melee_invisibility_restore():
    s=sim([actor('dushdo','d',1,route=route(1)),actor('player','p',1.2)]);s.ctx.spatial.blocking();assert s.ctx.spatial.blocked_by('d')==refs(s,'p');assert 9 not in state(s,'d')['abnormal_flags']
    s.session.advance(20);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['time']==17 and hits[0]['payload']['amount']==320
    s.submit({'action':'withdraw','source':'p'});s.session.advance(1);released=s.session.time-1;assert s.ctx.spatial.blocked_by('d') is None
    s.session.advance(89);assert 9 not in state(s,'d')['abnormal_flags'];s.session.advance(2);assert 9 in state(s,'d')['abnormal_flags']
def timing_cast_then_next_cycle():
    s=sim([actor('duholy','h',.5),actor('dushdo','d',1,route=route(1)),actor('player','p',1.2)]);s.ctx.spatial.blocking();s.session.advance(35)
    starts=[e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==refs(s,'d')];hits=[e['time'] for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==refs(s,'d')];assert starts[:2]==[0,27] and hits[:2]==[8,35][:len(hits[:2])]
    s=sim([actor('duholy','h',4),actor('dushdo','d',1,route=route(1)),actor('player','p',1.2)]);s.ctx.spatial.blocking();s.session.advance(5);s.ctx.effects.execute(refs(s,'h'),[refs(s,'h')],{'op':'move','position':{'row':1,'col':.5}});s.ctx.buffs.reconcile();assert abs(stat(s,'d','attack_interval')-.9)<1e-9 and s.ctx.get('d',('runtime','next_attack'))==63
    s.session.advance(60);hits=[e['time'] for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==refs(s,'d')];assert hits[0]==17;s.session.advance(10);hits=[e['time'] for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==refs(s,'d')];assert hits[1]==71
def typed_masks_and_invisible_targets():
    s=sim([actor('duholy','h',1,route=route(1)),actor('dushdo','d',1.1),actor('player','p',1.2)]);s.ctx.spatial.blocking();s.ctx.set(refs(s,'p'),('selection_state','motion'),2);assert s.ctx.spatial.select(refs(s,'h'),'selector/ch9/coupled/duholy/blocker')==[]
    s.ctx.set(refs(s,'p'),('selection_state','motion'),1);s.ctx.set(refs(s,'p'),('selection_state','abnormal_flags'),[9]);assert s.ctx.spatial.select(refs(s,'h'),'selector/ch9/coupled/duholy/blocker')==[]
def public_cpp_and_head():
    commands=[{'at':50,'action':'withdraw','source':'h1'},{'at':75,'action':'withdraw','source':'h2'},{'at':100,'action':'withdraw','source':'p'}];actors=[actor('duholy','h1',.5),actor('duholy','h2',.6),actor('dushdo','d',1,route=route(1)),actor('player','p',1.2)];p=package(actors,commands=commands);program=Compiler(providers=providers()).compile(p);s=Engine.create(program,providers=providers(),seed=9175);s.session.advance(45)
    LOG.mkdir(parents=True,exist_ok=True);path=LOG/'public.checkpoint.json';path.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(program,json.loads(path.read_bytes()),providers=providers());s.session.advance(160);r.session.advance(160);assert s.checkpoint()==r.checkpoint();head=replay(program,s.export_replay(),providers=providers());assert s.checkpoint()==head.checkpoint();assert 9 in state(s,'d')['abnormal_flags'];ARTIFACTS.append({'path':str(path),'sha256':sha(path),'cpp_equal':True,'public_replay_equal':True,'head_sha256':digest(s.checkpoint())})
def main():
    before=implementation_digest();assert before==CORE
    for name,fn in [('source_closure_and_unused_db_flame_reject',source_and_db_ownership),('single_pair_source_stats_effects',single_pair_stats),('native_vs_bb_radius_reference_boundaries',radius_profiles),('invisible_partner_reference_and_marker_loss',marker_visibility_profiles),('shared_multi_source_first_last_lifetimes',multiple_sources_last_departure),('silence_only_refraction',silence_and_aura),('real_block_arts_melee_restore_3_seconds',real_block_melee_invisibility_restore),('current_cast_and_next_sampled_schedule',timing_cast_then_next_cycle),('typed_melee_masks_and_invisible_targets',typed_masks_and_invisible_targets),('public_cpp_head_with_source_departures',public_cpp_and_head)]:case(name,fn)
    report={'core':implementation_digest(),'core_guard_equal':before==implementation_digest(),'actual_exit':0 if all(x['passed'] for x in RESULTS) else 1,'results':RESULTS,'artifacts':ARTIFACTS,'cleanup':CLEANUP,'raw_deleted':all(not Path(x['path']).exists() for x in ARTIFACTS),'whole_stage':False,'client_verified':False};REPORT.mkdir(parents=True,exist_ok=True);(REPORT/'author.v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
