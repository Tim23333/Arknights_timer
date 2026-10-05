import sys,json,copy,traceback,hashlib,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_finale_joint_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter09_mandra_v1.build import *
OUT=ROOT/'validation/campaign/chapter09_finale_joint_v1';LOG=Path(os.environ.get('ARKSIM_RUN_DIR','E:/ArkSimLogs/runs/chapter09_finale_mandra_focused_v1'));RESULTS=[];FACTS={};CLEAN=[];ARTIFACTS=[]
def fixture(profile='talent_prefix'):
    p=build(profile);p['entities'].append({'id':'unit/m/test/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':30000,'atk':1000,'def':100,'mres':20,'attack_speed_ratio':1,'block_count':2}},'resources':{'hp':{'role':'health','initial':30000,'capacity':30000}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/m/test/hit']}});p['selectors'].append({'id':'selector/m/test/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'},{'state':'alive'}],'limit':1});p['abilities'].append({'id':'ability/m/test/hit','kind':'ability','activation':{'mode':'manual'},'selector':'selector/m/test/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]});p['scenarioDraft']={'id':'scene/m/full','ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':7},'initialEntities':[{'definition':BODY,'instanceAlias':'boss','position':{'row':3,'col':3}},{'definition':'unit/m/test/player','instanceAlias':'player','position':{'row':3,'col':4}}],'commands':[]};return p
def sim(p=None):return Engine.create(Compiler(providers=providers()).compile(p or fixture()),providers=providers(),seed=1523)
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def hit(s,scale=1):s.ctx.effects.execute('player',['boss'],{'op':'damage','damage_type':'true','scale':scale})
def state(s):return s.ctx.get('boss',('behavior','state'))
def shield_and_actual_recovery_memory():
    p=fixture();p['scenarioDraft']['initialEntities'].append({'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':3,'col':2}});s=sim(p);hit(s);assert s.ctx.resources.current('boss','hp')==49600
    s.ctx.abilities.start('pillar','ability/ch9/pillar/collapse_right');s.advance(46);assert s.ctx.resources.current('boss','hp')==44800 and state(s)=='ground_open';record=next(b for b in s.ctx.get('boss',('buffs','instances')) if b['definition']==RECOVERY);assert abs(record['blackboard']['hp_ratio']-(44800/50000-.4))<1e-12
    hit(s,19);assert state(s)=='ground_open';hit(s,2);s.advance(1);assert state(s)=='ground_stone'
def two_life_profiles_and_modes():
    for profile,values in PROFILE.items():
        s=sim(fixture(profile));hit(s,130);assert s.ctx.resources.current('boss','hp')==0 and state(s)=='fly_stone' and not s.ctx.active('boss')
        assert s.ctx.get('boss',('spatial','motion_mode'))==1 and s.ctx.get('boss',('spatial','route_motion_mode'))==0
        clocks=s.ctx.get('boss',('runtime','cooldowns'));assert clocks[RAY]==values['ray_cd']*30 and clocks[SUMMON]==values['summon_cd']*30
        r=Engine.restore(s.program,cp(s),providers=providers());s.advance(151);r.advance(151);assert cp(s)==cp(r) and s.ctx.resources.current('boss','hp')==50000 and s.ctx.active('boss')
        hit(s,130);assert not s.ctx.alive('boss')
def ray_current_target_and_slow():
    s=sim();s.advance(150);assert not [e for e in s.session.events if e['type']=='attachment.packet'];s.advance(12)
    packets=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload'].get('ability')==RAY];assert packets
    assert s.ctx.resources.current('player','hp')==29488 and abs(s.ctx.attributes.value('player','attack_speed_ratio')-.3)<1e-12
    s.ctx.resources.adjust('player','hp',value=25000);s.advance(30);assert s.ctx.resources.current('player','hp')==24488
    s.ctx.lifecycle.retire('player','withdrawn');s.advance(2);tokens=[e for e in s.session.world.entities() if e['definition_id']=='unit/'+PREFIX+'sealed_ground'];assert len(tokens)==1;pos=tokens[0]['components']['spatial']['position'];tile=s.ctx.spatial.grid.tile(pos['row'],pos['col']);assert tile['buildableType']==0 and tile['passableMask']==2
    FACTS['ray']={'packet_health':512,'slow_ratio':.3,'source047_spawned':True,'position':dict(pos)}
def summon_real_and_auto5():
    s=sim();hit(s,130);s.advance(650);tokens=[e for e in s.session.world.entities() if e['definition_id']=='unit/'+PREFIX+'auto_pillar'];assert tokens
    token=tokens[0]['id'];assert s.ctx.resources.current(token,'hp')==5000 and s.ctx.resources.current(token,'sp')==10
    born=next(e['time'] for e in s.session.events if e['type']=='entity.created' and (e['payload'].get('entity')==token or e['payload'].get('target')==token))
    s.advance(born+151-s.session.time);started=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==token];assert started and started[0]['time']==born+150
    s.advance(46);assert not s.ctx.alive(token)
def public_cpp_head():
    p=fixture();p['scenarioDraft']['commands']=[{'at':0,'action':'skill','source':'player','ability':'ability/m/test/hit'}];s=sim(p);s.advance(160);LOG.mkdir(parents=True,exist_ok=True);path=LOG/'ray.public.checkpoint.json';path.write_text(json.dumps(s.checkpoint()),encoding='utf8');ARTIFACTS.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size});r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=providers());s.advance(65);r.advance(65);assert cp(s)==cp(r);h=replay(s.program,s.export_replay(),providers=providers());assert cp(h)==cp(s)
def actual_four_mode_animations():
    for index,mode in enumerate(['ground_stone','ground_open','fly_stone','fly_open']):
        p=fixture();boss=next(e for e in p['entities'] if e['id']==BODY);p['behaviors'][0]['initial']=mode
        for ability in p['abilities']:
            if ability['id'] in [RAY,SUMMON]:ability['activation']['condition']='False'
        if index<2:
            target=next(e for e in p['entities'] if e['id']=='unit/m/test/player');target['components']['deployable']={'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'};p['scenarioDraft']['initialEntities'][1]['position']={'row':3,'col':3};p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':'WALK','startPosition':{'row':3,'col':3},'endPosition':{'row':3,'col':6},'checkpoints':[]}
        s=sim(p)
        if index<2:s.ctx.spatial.blocking();assert s.ctx.spatial.blocked_by('boss')==s.session.world.resolve('player')
        s.advance(25);assert s.ctx.resources.current('player','hp')==30000;s.advance(1)
        if index>=2:
            assert s.ctx.resources.current('player','hp')==30000 and any(e['type']=='projectile.launched' and e['time']==25 for e in s.session.events);s.advance(4)
        assert s.ctx.resources.current('player','hp')==29488
        accepted=[e for e in s.session.events if e['type']=='damage.accepted'];assert accepted[0]['time']==(25 if index<2 else 28)
def whole_two_life_public_cpp():
    p=fixture();p['abilities'].append({'id':'ability/m/test/lethal','kind':'ability','activation':{'mode':'manual'},'selector':'selector/m/test/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':130}}]});next(e for e in p['entities'] if e['id']=='unit/m/test/player')['components']['abilities'].append('ability/m/test/lethal');p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'player','ability':'ability/m/test/lethal'},{'at':201,'action':'skill','source':'player','ability':'ability/m/test/lethal'}]
    s=sim(p);s.advance(8);checkpoint=cp(s);r=Engine.restore(s.program,checkpoint,providers=providers());s.advance(220);r.advance(220);assert cp(s)==cp(r) and not s.ctx.alive('boss');h=replay(s.program,s.export_replay(),providers=providers());assert cp(h)==cp(s)

def recovery_native_25_and_pending_cancel():
    p=fixture();p['scenarioDraft']['initialEntities'].append({'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':3,'col':2}});s=sim(p);s.ctx.abilities.start('pillar','ability/ch9/pillar/collapse_right');s.advance(46);assert state(s)=='ground_open';s.advance(749);assert state(s)=='ground_open';s.advance(1);assert state(s)=='ground_stone';s.advance(60)
    started=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']=='ability/'+PREFIX+'restore_skin'];assert started;assert not any(b['definition']=='buff/'+PREFIX+'pending_skin' for b in s.ctx.get('boss',('buffs','instances')))
    s=sim(p);s.ctx.abilities.start('pillar','ability/ch9/pillar/collapse_right');s.advance(46);hit(s,21);s.advance(1);assert state(s)=='ground_stone' and any(b['definition']=='buff/'+PREFIX+'pending_skin' for b in s.ctx.get('boss',('buffs','instances')));before_hp=s.ctx.resources.current('boss','hp');r=Engine.restore(s.program,cp(s),providers=providers());s.advance(40);r.advance(40);assert cp(s)==cp(r) and s.ctx.resources.current('boss','hp')==before_hp;s.ctx.lifecycle.retire('boss','withdrawn');s.advance(400);assert not s.ctx.get('boss',('runtime','casts'),{})

def actual_highest_modified_atk_and_cancel():
    p=fixture();p['buffs'].append({'id':'buff/m/test/atk','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':3000}]});second=copy.deepcopy(p['entities'][-1]);second['id']='unit/m/test/second';second['components']['attributes']['base']['atk']=50;second['components']['buffs']={'initial':['buff/m/test/atk']};p['entities'].append(second);p['scenarioDraft']['initialEntities'].append({'definition':second['id'],'instanceAlias':'second','position':{'row':4,'col':3}});s=sim(p);s.advance(162);assert s.ctx.resources.current('second','hp')==29488 and s.ctx.resources.current('player','hp')==30000
    s.ctx.buffs.apply('boss','boss','buff/ch9/pillar/stun10');s.advance(1);assert not s.ctx.get('boss',('runtime','casts'),{}) and not s.ctx.get('boss',('attachments','instances'),[])

def strict_tile_and_trigger_rejection():
    from ark_sim.domains.abilities import ActivationRejected
    s=sim();s.ctx.buffs.apply('boss','boss','buff/ch9/pillar/stun10');before=cp(s)
    try:s.ctx.effects.execute('boss',['boss'],{'op':'trigger_ability','ability':'ability/'+PREFIX+'restore_skin'})
    except ActivationRejected:pass
    else:raise AssertionError('default controlled request accepted')
    assert cp(s)==before;s.ctx.effects.execute('boss',['boss'],{'op':'trigger_ability','ability':'ability/'+PREFIX+'restore_skin','parameters':{'on_rejection':'skip'}});assert s.ctx.resources.current('boss','hp')==50000
    for bad in [True,0,'ignore']:
        p=fixture();next(b for b in p['buffs'] if b['id']=='buff/'+PREFIX+'pending_skin')['effects'][0]['parameters']['on_rejection']=bad
        try:sim(p)
        except ValueError:pass
        else:raise AssertionError('bad rejection policy compiled')
    p=fixture();next(a for a in p['abilities'] if a['id']=='ability/'+PREFIX+'restore_skin')['activation'].setdefault('on_start',[]).append({'op':'random','stream':'late','probability':1,'on_success':[{'op':'modify_resource','resource':'missing','amount':1}]});s=sim(p);before=cp(s);draws=[];sample=s.session.random.sample
    def observed_sample(stream):draws.append(stream);return sample(stream)
    s.session.random.sample=observed_sample
    try:s.ctx.effects.execute('boss',['boss'],{'op':'trigger_ability','ability':'ability/'+PREFIX+'restore_skin','parameters':{'on_rejection':'skip'}})
    except ValueError as error:assert str(error)=="resource 'missing' is absent on 2"
    else:raise AssertionError('skip swallowed late resource fault')
    assert draws==['late'] and cp(s)==before;FACTS['late_fault']={'error':"resource 'missing' is absent on 2",'observed_random_streams':draws,'complete_checkpoint_rollback':True}
    s=sim();s.ctx.abilities.start('boss',TILE,automatic=True,event_payload={'target':s.session.world.resolve('player'),'position':{'row':3,'col':5}});cast=list(s.ctx.get('boss',('runtime','casts')).values())[0];a=s.program.definitions[TILE];before=cp(s)
    try:s.ctx.effects.execute('boss',['boss'],a['timeline'][0]['effect'],ability=a,cast=cast)
    except ValueError as error:assert str(error)=='Tile effect requires current scheduled task of actual owned cast'
    else:raise AssertionError('static actual cast borrowed tile task')
    assert cp(s)==before;s.advance(1);assert any(e['definition_id']=='unit/'+PREFIX+'sealed_ground' for e in s.session.world.entities())


def stone_area_native_radius_and_types():
    p=fixture();p['behaviors'][0]['initial']='fly_stone'
    for a in p['abilities']:
        if a['id'] in [RAY,SUMMON] or a['id'].startswith('ability/'+PREFIX+'normal_'):a['activation']['condition']='False'
    for name,col,category in [('outside',5,1),('trap',4,2)]:
        e=copy.deepcopy(next(e for e in p['entities'] if e['id']=='unit/m/test/player'));e['id']='unit/m/test/'+name;e['components']['selection_state']['category']=category;p['entities'].append(e);p['scenarioDraft']['initialEntities'].append({'definition':e['id'],'instanceAlias':name,'position':{'row':3,'col':col}})
    s=sim(p);s.advance(31);assert abs(s.ctx.resources.current('player','hp')-29846.4)<1e-9 and s.ctx.resources.current('outside','hp')==30000 and s.ctx.resources.current('trap','hp')==30000;assert s.ctx.get('boss',('spatial','motion_mode'))==1 and s.ctx.get('boss',('spatial','route_motion_mode'))==0

def public_summon_auto_full_head():
    p=fixture();p['abilities'].append({'id':'ability/m/test/lethal','kind':'ability','activation':{'mode':'manual'},'selector':'selector/m/test/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':130}}]});next(e for e in p['entities'] if e['id']=='unit/m/test/player')['components']['abilities'].append('ability/m/test/lethal');p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'player','ability':'ability/m/test/lethal'}]
    s=sim(p);s.advance(660);token=next(e for e in s.session.world.entities() if e['definition_id']=='unit/'+PREFIX+'auto_pillar');assert s.ctx.resources.current(token['id'],'hp')==5000;r=Engine.restore(s.program,cp(s),providers=providers());s.advance(210);r.advance(210);assert cp(s)==cp(r) and not s.ctx.alive(token['id']);h=replay(s.program,s.export_replay(),providers=providers());assert cp(h)==cp(s)

def cleanup():
    if LOG.exists() and any(LOG.iterdir()):
        r=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs_v2.py'),'--run-dir',str(LOG),'--apply','--minimum-age-minutes','0','--completed-pid',str(os.getpid())],capture_output=True,text=True,encoding='utf8');assert r.returncode==0;CLEAN.append(json.loads(r.stdout))
def main():
    guard=implementation_digest();guard_paths=[CAND/'ark_sim/rules/contracts.json',Path(__file__),ROOT/'tools/chapter09_mandra_v1/build.py',REQ,SOURCE,DETAIL,TOKEN,ROOT/'tools/chapter09_pillar_lifecycle_v1/build.py',ROOT/'tools/chapter09_pillar_v1/build_payload.py'];guards={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guard_paths}
    for fn in [shield_and_actual_recovery_memory,two_life_profiles_and_modes,ray_current_target_and_slow,public_cpp_head,strict_tile_and_trigger_rejection]:
        try:fn();RESULTS.append({'case':fn.__name__,'passed':True})
        except Exception as error:RESULTS.append({'case':fn.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
        finally:cleanup()
    r={'core_before':guard,'core_after':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in RESULTS) else 1,'results':RESULTS,'facts':FACTS,'artifacts':ARTIFACTS,'cleanup':CLEAN,'raw_deleted_during_worker':all(not Path(x['path']).exists() for x in ARTIFACTS),'raw_cleanup_owner':'run_with_log_cleanup outer wrapper','source_helpers_before':guards,'source_helpers_after':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guard_paths}};(OUT/'mandra.focused.v1.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r));return r['actual_exit']
if __name__=='__main__':raise SystemExit(main())
