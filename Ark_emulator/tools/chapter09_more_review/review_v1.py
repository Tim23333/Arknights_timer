"""Independent new fixtures for three ordinary source modules, fixed 82 runtime."""
import sys,json,hashlib,copy,traceback,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_campaign_foundation_v5_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import digest
# Import actual content policy providers; never import any author's test fixture.
from tools.chapter09_more_content.build_v1 import providers
REG=providers();CORE='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
MODULEDIR=ROOT/'packages/campaign/chapter09_consumers/more_ordinary'
MODULES={n:json.loads(next(MODULEDIR.glob('*_'+n+'.module.v1.json')).read_bytes()) for n in ('dushld','duphlx','dumage')}
PINS={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in MODULEDIR.glob('*.module.v1.json')}
LOG=Path('E:/ArkSimLogs/runs/chapter09_more_independent');OUT=ROOT/'validation/campaign/chapter09_more_independent'
RESULTS=[];ARTIFACTS=[];CLEANUPS=[]
def eid(name):return MODULES[name]['entities'][0]['id']
def scene(actors,extra=None):
    d={'schemaVersion':2}
    for m in MODULES.values():
        for k,v in m.items():
            if k not in ('manifest','schemaVersion'):d.setdefault(k,[]).extend(copy.deepcopy(v))
    d['entities'].append({'id':'peer/probe','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':9000,'atk':1,'def':100,'mres':0}},'resources':{'hp':{'initial':9000,'capacity_attribute':'max_hp','role':'health'}},'selection_state':{'side':1,'motion':1,'category':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    d['scenarioDraft']={'id':'peer/more','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':12},'resources':{'dp':{'initial':100,'capacity':1000}},'initialEntities':actors}
    if extra:extra(d)
    pr=Compiler(providers=REG).compile(d);return Engine.create(pr,seed=719,providers=REG)
def actor(name,alias,col,row=2,components=None):
    return {'definition':eid(name) if name in MODULES else 'peer/probe','instanceAlias':alias,'position':{'row':row,'col':col},**({'components':components} if components else {})}
def ref(s,x):return s.session.world.resolve(x)
def attr(s,x,k):return s.ctx.attributes.value(x,k)
def sel(s,x,name):return s.ctx.spatial.select(ref(s,x),'selector/ch9/'+name,ability=s.program.definitions.get('ability/ch9/dumage/attack',{}))
def cleanup():
    p=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs.py'),'--apply','--run-dir',str(LOG),'--minimum-age-minutes','0','--completed-pid',str(os.getpid())],capture_output=True,text=True,encoding='utf8',check=True);CLEANUPS.append(json.loads(p.stdout.strip()))
def case(name,fn):
    try:fn();RESULTS.append({'case':name,'passed':True})
    except Exception as e:RESULTS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    finally:
        if LOG.exists() and any(LOG.glob('*.json')):cleanup()
def rawfields():
    native=json.loads((ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json').read_bytes())
    for n,m in MODULES.items():
        md=m['manifest']['metadata'];row=native['variants'][md['native_variant']];stats=row['native_enemy']['resolved']['attributes'];base=m['entities'][0]['components']['attributes']['base']
        for nativekey,key in [('maxHp','max_hp'),('atk','atk'),('def','def'),('magicResistance','mres'),('moveSpeed','move_speed'),('baseAttackTime','attack_interval'),('massLevel','mass_level')]:assert base[key]==stats[nativekey],(n,key)
        assert md['source_passive_closure']==row['passive_and_skill_components']
        raw=md['source_combat']['raw'];assert raw==row['modes'][0]['nodes']['_combat']['raw'];effect=m['abilities'][0]['timeline'][0]['effect'];assert effect['scale']==raw['_atkScale'];assert effect['damage_type']==('arts' if raw['_damageType']==2 else 'physical')
        bb={x['key']:x['value'] for x in row['native_enemy']['resolved']['talentBlackboard']};refract=next(b for b in m['buffs'] if b['id'].endswith('/refracting'));assert refract['modifiers'][0]['value']==bb['refracting.magic_resistance']==70
        if n=='duphlx':assert next(b for b in m['buffs'] if b['id'].endswith('/def200'))['modifiers'][0]['value']==bb['auraDefup.def']==200
        assert m['abilities'][0]['metadata']['source_OnAttack_frame']==md['source_combat']['animation_binding']['events'][0]['frame']
        for p,h in md['source_locks'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    p=MODULES['duphlx'];md=p['manifest']['metadata'];closure=md['source_passive_closure'];a=next(x for x in closure if x['class']=='AuraAbility')['raw'];v=next(x for x in closure if x['class']=='FilterBuffTargetValidator')['raw'];assert a['_selfOption']==2 and a['_removeBuffWhenTargetLeave']==1 and a['_removeBuffWhenAbilityDetached']==1;assert v['_buffs']==['duphlx_mask'] and v['_excludeKey']==0
    assert p['selectors'][1]['region']['radius']==md['source_geometry']['raw']['m_Radius']==1
def aura_boundaries():
    for dist,yes in [(1,True),(1+1e-7,False),(.9999999,True)]:
        s=scene([actor('duphlx','a',3),actor('duphlx','b',3+dist)]);assert attr(s,'a','def')==(500 if yes else 300);assert attr(s,'b','def')==(500 if yes else 300)
    s=scene([actor('duphlx','a',3)]);assert attr(s,'a','def')==300;assert sel(s,'a','duphlx/aura')==[]
def aura_masks():
    for field,value,yes in [('side',1,True),('side',2,False),('side',0,False),('motion',2,True),('motion',0,False),('category',2,False),('target_free',True,False),('ally_target_free',True,False),('camouflage',True,False)]:
        c={'selection_state':{field:value},'buffs':{'initial':['buff/ch9/duphlx/mask']}}
        s=scene([actor('duphlx','a',3),actor('probe','b',3.5,components=c)]);actual=attr(s,'b','def');assert actual==(300 if yes else 100),(field,value,actual)
def aura_stacking_exit():
    s=scene([actor('duphlx','a',3),actor('duphlx','b',3.5),actor('duphlx','c',4)]);assert [attr(s,x,'def') for x in ('a','b','c')]==[700,700,700]
    s.ctx.lifecycle.retire(ref(s,'a'),'retired');s.ctx.buffs.reconcile();assert [attr(s,x,'def') for x in ('b','c')]==[500,500]
    s.ctx.set(ref(s,'c'),('spatial','position'),{'row':2,'col':7});s.ctx.buffs.reconcile();assert [attr(s,x,'def') for x in ('b','c')]==[300,300]
def marker():
    s=scene([actor('duphlx','a',3),actor('probe','b',3.5)]);assert attr(s,'b','def')==100
    uid=s.ctx.buffs.apply(ref(s,'b'),ref(s,'b'),'buff/ch9/duphlx/mask');s.ctx.buffs.reconcile();assert attr(s,'b','def')==300
    s.ctx.buffs.remove(ref(s,'b'),uid);s.ctx.buffs.reconcile();assert attr(s,'b','def')==100
def marker_disabled():
    def extra(d):
        b=next(b for b in d['buffs'] if b['id']=='buff/ch9/duphlx/mask');b['active_rule']='peer/marker_active'
        d['rules'].append({'id':'peer/marker_active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'12 not in inputs.status.abnormal_flags'}})
    s=scene([actor('duphlx','a',3),actor('probe','b',3.5,components={'buffs':{'initial':['buff/ch9/duphlx/mask']},'selection_state':{'abnormal_flags':[12]}})],extra)
    assert attr(s,'b','def')==100;s.ctx.set(ref(s,'b'),('selection_state','abnormal_flags'),[]);s.ctx.buffs.applicability.reconcile();s.ctx.buffs.reconcile();assert attr(s,'b','def')==300
def refraction():
    for n,base in [('dushld',0),('duphlx',0),('dumage',20)]:
        s=scene([actor(n,'a',3)]);assert attr(s,'a','mres')==base+70;s.ctx.set(ref(s,'a'),('selection_state','abnormal_flags'),[12]);s.ctx.buffs.applicability.reconcile();assert attr(s,'a','mres')==base;s.ctx.set(ref(s,'a'),('selection_state','abnormal_flags'),[]);s.ctx.buffs.applicability.reconcile();assert attr(s,'a','mres')==base+70
def caster_selector():
    radius=2.0999999046325684
    for distance,yes in [(radius,True),(radius+1e-7,False)]:
        s=scene([actor('dumage','a',0),actor('probe','b',distance,components={'selection_state':{'side':0}})]);assert (ref(s,'b') in sel(s,'a','dumage/range'))==yes
    for field,value in [('side',1),('motion',2),('category',2),('target_free',True),('camouflage',True)]:
        c={'selection_state':{'side':0,field:value}};s=scene([actor('dumage','a',3),actor('probe','b',4,components=c)]);assert ref(s,'b') not in sel(s,'a','dumage/range'),(field,value)
def projectile(retire=None):
    s=scene([actor('dumage','a',3),actor('probe','b',5)]);a,b=ref(s,'a'),ref(s,'b');eff=copy.deepcopy(MODULES['dumage']['abilities'][0]['timeline'][0]['effect']);s.ctx.effects.execute(a,[b],eff)
    assert s.ctx.resources.current(b,'hp')==9000;s.ctx.set(a,('attributes','base','atk'),600);s.ctx.set(b,('attributes','base','mres'),50);s.ctx.set(b,('spatial','position'),{'row':2,'col':7})
    if retire=='withdraw':s.submit({'action':'withdraw','source':'a'},at=0)
    elif retire=='dead':s.ctx.lifecycle.retire(a,'dead')
    elif retire=='target':s.ctx.lifecycle.retire(b,'dead')
    elif retire=='cancel':
        x=s.ctx.projectiles._get('projectile/1');s.ctx.projectiles._finish(x,'peer_cancel')
    LOG.mkdir(parents=True,exist_ok=True);path=LOG/('mage_'+str(retire)+'.checkpoint.json');path.write_text(json.dumps(s.checkpoint()),encoding='utf8');cp=json.loads(path.read_bytes());r=Engine.restore(s.program,cp,providers=REG)
    s.session.advance(24);r.session.advance(24);assert s.checkpoint()==r.checkpoint()
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==(0 if retire in ('target','cancel') else 1),(retire,hits)
    if hits:assert s.ctx.resources.current(b,'hp')==8700,(retire,s.ctx.resources.current(b,'hp'))
    if retire=='withdraw':assert not s.ctx.active(a),s.ctx.get(a,('runtime',))
    ARTIFACTS.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'head_sha256':digest(s.checkpoint()),'checkpoint_equal':True})
def main():
    assert implementation_digest()==CORE
    for n,f in [('raw_source_fields_and_pins',rawfields),('aura_radius_self_exclusion',aura_boundaries),('aura_side_motion_category_free_masks',aura_masks),('aura_multi_source_stacking_retire_leave',aura_stacking_exit),('aura_missing_and_removed_marker',marker),('aura_disabled_marker_applicability',marker_disabled),('live_refraction_res_silence',refraction),('caster_radius_and_typed_masks',caster_selector),('caster_homing_live_atk_res_cpp_head',lambda:projectile()),('caster_retained_public_withdraw_cpp_head',lambda:projectile('withdraw')),('caster_retained_dead_cpp_head',lambda:projectile('dead')),('caster_dead_target_cpp_head',lambda:projectile('target')),('caster_cancel_cpp_head',lambda:projectile('cancel'))]:case(n,f)
    after={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in PINS};assert after==PINS and implementation_digest()==CORE
    import ark_sim
    report={'core':CORE,'candidate_import_path':str(Path(ark_sim.__file__).resolve()),'core_guard_before_after_equal':True,'module_pins':PINS,'module_guard_equal':True,'fixture_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'actual_exit':0 if all(x['passed'] for x in RESULTS) else 1,'results':RESULTS,'artifacts':ARTIFACTS,'cleanup':CLEANUPS,'raw_deleted':all(not Path(a['path']).exists() for a in ARTIFACTS),'author_fixture_imported':False,'root_fixture_imported':False,'actual_content_provider_used':'tools.chapter09_more_content.build_v1.providers (callables only; no author fixture/build invocation)','whole_stage':False,'client_verified':False}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'report.v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
