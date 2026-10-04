"""Read-only coherent projectile peer; independent values, actual asset bytes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.experiments.m17_peer import probe as h,extended as e,trajectory_probe as bad,callback_chain_probe as chain
from copy import deepcopy
import hashlib,json
import UnityPy
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.domains.providers import BUILTIN_PROVIDERS
OUT=h.ROOT/'validation/campaign/m17_peer_final';OUT.mkdir(parents=True,exist_ok=True)
FILES={};LAST=None;current=None;inputs=[]
def read(path,pin=None):
    raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if pin is not None:assert sha==pin,str(path)
    FILES[str(path)]=sha;return json.loads(raw)
def source_values():
    source_path=h.ROOT/'packages/campaign/chapter01_models/projectile_lifecycle/source.reference.json'
    j=read(source_path);cache={}
    def objects(record):
        p=h.ROOT.parent/record['path'];raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==record['sha256'];FILES[str(p)]=sha
        if p not in cache:cache[p]={o.path_id:o for o in UnityPy.load(str(p)).objects}
        return cache[p]
    for record in j['actual_projectile_components']:
        assert objects(record['asset'])[record['component_path_id']].read_typetree()==record['actual_typetree']
        script=objects(record['MonoScript_source'])[record['MonoScript_path_id']].read_typetree();assert script['m_ClassName']==record['actual_native_class']
    n=next(x['actual_typetree'] for x in j['actual_projectile_components'] if x['projectile_key']=='projectile_enemy_cqbw' and x['actual_native_class']=='SimpleProjectile')
    c=next(x['actual_typetree'] for x in j['actual_projectile_components'] if x['projectile_key']=='projectile_enemy_cqbw_s1' and x['actual_native_class']=='SimpleProjectile')
    assert (n['_lifeTime'],n['_maxHitNum'],n['_canHitSameTargetMultipleTimes'],n['_stopAfterMaxHit'],n['_stopWhenSourceInvalid'])==(10,1,0,1,0)
    assert abs(c['_lifeTime']-3.2)<1e-6 and (c['_maxHitNum'],c['_stopAfterMaxHit'],c['_alwaysHitTraceTargetInTheEnd'])==(1,0,1)
    native=read(h.ROOT/'packages/campaign/chapter01_sources/native.reference.json','a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd')
    enemy=native['enemies']['enemy_1504_cqbw'];assert enemy['native_enemy']['resolved']['attributes']['atk']==470
    for a in j['actual_RangedAttack_components']:
        assert objects(enemy['prefab']['source'])[a['path_id']].read_typetree()==a['raw'] and a['raw']['_useCachedAtkOnly']==0
    return {'actual_components':len(j['actual_projectile_components']),'native_normal_lifetime':10,'native_C4_lifetime_float':c['_lifeTime'],
      'model_clock_3_2_snap96_ticks_not_native_rounding_proof':True,'native_bodies_recovered':False}
def fixed_or_follow(attachment):
    p=h.scene()
    if attachment=='follow':
        q=read(h.ROOT/'packages/campaign/chapter01_models/projectile_lifecycle/follow.model.json')
        p['projectiles']=deepcopy(q['projectiles'])
    target=next(x for x in p['entities'] if x['id']=='unit/chapter01_w_target');target['components']['abilities']=['ability/shift']
    p['abilities'].append({'id':'ability/shift','kind':'ability','activation':{'mode':'manual','on_start':[
       {'op':'move','target':'source','position':{'row':3,'col':7}}]},'timeline':[]})
    s=h.make(p);s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0)
    s.submit({'action':'skill','source':'target0','ability':'ability/shift'},at=50);s.advance(114)
    assert not [x for x in s.session.events if x['type']=='damage.accepted']
    assert next(iter(s.ctx.get('w',('runtime','casts')).values()))['pending_projectiles']==1
    s.advance(1);areas=[x for x in s.session.events if x['type']=='area.resolved'];assert len(areas)==1
    assert areas[0]['payload']['center']=={'row':3,'col':4 if attachment=='fixed' else 7}
    assert s.ctx.resources.current('target0','hp')==(5000 if attachment=='fixed' else 4254) and s.ctx.resources.current('target1','hp')==4254
    assert not s.ctx.get('w',('runtime','casts'));h.roundtrip(s)
def half_open_life_and_one_hit():
    p=h.fixture(h.read(h.PACKAGE,h.PIN),positions=((3,4),));d=p['projectiles'][0]
    d['lifetime_seconds']=.1;d['motion']['parameters']['speed']=0;d['collision']['parameters']['enabled']=False
    s=h.make(p);s.advance(27)
    assert [x['time'] for x in s.session.events if x['type']=='damage.accepted']==[12,26]
    collisions=[x for x in s.session.events if x['type']=='calculation' and x['payload'].get('calculation_id')=='projectile.collision']
    assert [x['time'] for x in collisions]==[10,11,24,25] # no live step at expiry12/26
    instances=s.ctx.get('system/battle',('projectiles','instances'));assert all(x['hit_count']==1 and x['state']=='invalid' and not x['jobs'] for x in instances.values())
    h.roundtrip(s)
def eager_collision(inputs,params,context):
    return {'hits':[inputs['projectile']['trace_target'],inputs['projectile']['trace_target']],'terrain_hit':False,'stop':False}
eager_collision.version='independent-duplicate-trace-collision-v1'
def quota_duplicate_collision_cannot_double_settle():
    p=h.fixture(h.read(h.PACKAGE,h.PIN),positions=((3,4),));p['rules'].append({'id':'rule/eager','kind':'calculation_rule','contract':'projectile.collision',
      'implementation':{'type':'provider','provider':'peer.eager'}});p['projectiles'][0]['collision']['rule']='rule/eager'
    providers={**BUILTIN_PROVIDERS,'peer.eager':eager_collision}
    s=Engine.create(Compiler(providers=providers).compile(p),seed=1717,providers=providers);h.LAST=s
    s.advance(26);hits=[x for x in s.session.events if x['type']=='damage.accepted'];assert [x['time'] for x in hits]==[10,24] and all(x['payload']['amount']==370 for x in hits)
    assert all(x['hit_count']==1 and len(x['hit_targets'])==1 for x in s.ctx.get('system/battle',('projectiles','instances')).values())
    r=Engine.restore(s.program,s.checkpoint(),providers=providers);s.advance(2);r.advance(2)
    from ark_sim.tools.replay import replay
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers).snapshot()
def real_retired_source_retains_launched_only():
    p=h.fixture(h.read(h.PACKAGE,h.PIN),positions=((3,5),));e.director(p,[{'op':'retire','target':2,'parameters':{'reason':'dead'}}])
    s=h.make(p);s.submit({'action':'skill','source':'director','ability':'ability/peer_director'},at=10);s.advance(36)
    hits=[x for x in s.session.events if x['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['time']==21 and hits[0]['payload']['amount']==370
    assert not s.ctx.alive('w') and len([x for x in s.session.events if x['type']=='projectile.launched'])==1;h.roundtrip(s)
def typed_schema_and_references():
    changes=[lambda p:p['projectiles'][0].update(max_hits=True),lambda p:p['projectiles'][0].update(lifetime_seconds=float('nan')),
      lambda p:p['projectiles'][0]['lifecycle'].update(target_hidden='ignore'),lambda p:p['projectiles'][0]['motion'].update(rule='rule/ark_projectile_speed'),
      lambda p:p['projectiles'][0]['collision'].update(allow_other_targets=1),lambda p:p['abilities'][0]['timeline'][0]['effect'].update(projectile_definition='unit/chapter01_w')]
    rejected=[]
    for mutate in changes:
        # Every mutated normal projectile must be in the actual active closure.
        p=h.fixture(h.read(h.PACKAGE,h.PIN),positions=((3,4),));mutate(p)
        try:Compiler().compile(p)
        except (ValueError,TypeError):rejected.append(True)
        else:raise AssertionError('invalid projectile type/reference accepted')
    return {'negative_variants':len(rejected)}
if __name__=='__main__':
    core=implementation_digest();assert core==h.CORE
    for f in [Path(__file__),Path(h.__file__),Path(e.__file__),Path(bad.__file__),Path(chain.__file__),h.ROOT/'tools/build_chapter01_w_combat.py',
      h.RUNTIME/'ark_sim/rules/contracts.json',h.RUNTIME/'ark_sim/content/presets/ark_standard.json']:
        FILES[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    source=source_values();read(h.PACKAGE,h.PIN)
    read(h.ROOT/'packages/campaign/chapter01_models/projectile_lifecycle/follow.model.json')
    start=dict(FILES);BaseCompiler=Compiler
    class InputCompiler(BaseCompiler):
        def compile(self,data,*args,**kwargs):
            path=OUT/'fixtures'/f'{len(inputs)+1:02d}_{current}.json';path.parent.mkdir(parents=True,exist_ok=True)
            # One intentional NaN negative remains a diagnostic Python-JSON input;
            # the real Compiler, not this recorder, must reject its numeric type.
            path.write_bytes((json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=True)+'\n').encode())
            raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
            inputs.append({'case':current,'path':str(path),'sha256_before_decode':sha,'invalid_nonfinite_negative':b'NaN' in raw})
            return super().compile(json.loads(raw),*args,**kwargs)
    Compiler=InputCompiler;h.Compiler=InputCompiler;bad.Compiler=InputCompiler;cases=[]
    functions=[('hidden_C4_neighbor',h.hidden_C4_retains_point_hits_visible_neighbor),('C4_hit_time_stats',e.C4_hit_time_source_stat),
      ('normal_SP_claims',e.normal_cast_claim_two_frames_multiple_pending_groups),('captured_moving_target',e.moving_captured_target_never_retargets_nearer_neighbor),
      ('invalid_callback_rollback',e.invalid_callback_rolls_back_and_wait_claim_preserved),('typed_trajectory_output',bad.case),
      ('fixed_C4',lambda:fixed_or_follow('fixed')),('follow_C4',lambda:fixed_or_follow('follow')),('half_open_lifetime',half_open_life_and_one_hit),
      ('maxhit_duplicate',quota_duplicate_collision_cannot_double_settle),('retired_source_packet',real_retired_source_retains_launched_only),
      ('callback_child_wait_group',chain.case),('typed_schema_reference',typed_schema_and_references)]
    for current,fn in functions:
        h.LAST=None
        try:result=fn();c={'case':current,'result':'passed','summary':result}
        except Exception as error:c={'case':current,'result':'failed','error':repr(error)}
        if h.LAST is not None:
            s=h.LAST;c.update({'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'commands':s.export_replay(),
              'initial_scenario':thaw(s.program.scenario),'snapshot':s.snapshot(),'events':[thaw(x) for x in s.session.events]})
        cases.append(c)
    end={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in FILES};stable=all(end[p]==v for p,v in start.items()) and implementation_digest()==core and all(hashlib.sha256(Path(i['path']).read_bytes()).hexdigest()==i['sha256_before_decode'] for i in inputs)
    passed=stable and all(c['result']=='passed' for c in cases)
    value={'schema':'ark-sim/projectile-independent-peer/v1','passed':passed,'core_start':core,'core_end':implementation_digest(),
      'source_start':start,'source_end':end,'identity_stable':stable,'runtime_module':h.ark_sim.__file__,'actual_source_values':source,
      'fixture_inputs':inputs,'cases':cases,'formal_approval':False,'review_receipt':False,'scope':'Declared projectile model only; no native callback/body/full Boss/stage'}
    (OUT/'report.json').write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'passed':passed,'core':core,'cases':[{k:v for k,v in c.items() if k in ('case','result','error')} for c in cases]}))
    raise SystemExit(0 if passed else 1)
