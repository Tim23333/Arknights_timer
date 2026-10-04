"""Current M21 combination only; isolated interactions plus untouched stage prefixes."""
import sys
from pathlib import Path
import hashlib,json
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m21_integration_candidate'
CORE='c069e0206c076b429750b3fd97a507c54fb8e34fee51376c2f979f434151b95e'
PINS={'01-11':'2fd475a0491c86b0ab8d48ff1a17b983e5156d23bc5ea20a77782c8484e77e33','01-12':'9aa6f6b6aceb2eb1f2ced0013025765742f305d2b31dbf045e6c13201424154d'}
sys.path.insert(0,str(RUNTIME))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
OUT=ROOT/'validation/campaign/m21_peer';OUT.mkdir(parents=True,exist_ok=True)
FILES={};INPUTS=[];LAST=None;NAME=None
def read(path,pin=None):
    raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if pin:assert sha==pin,str(path)
    FILES[str(path)]=sha;return json.loads(raw)
def package(stage):return read(ROOT/f'packages/campaign/chapter01_stage_models/m21/level_main_{stage}.partial.json',PINS[stage])
def make(data):
    global LAST
    path=OUT/'fixtures'/f'{len(INPUTS)+1:02d}_{NAME}.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode());raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    INPUTS.append({'case':NAME,'path':str(path),'sha256_before_decode':sha})
    LAST=Engine.create(Compiler().compile(json.loads(raw)),seed=2121);return LAST
def cp(s):
    r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def add_actor(p,key,tags,abilities=(),hp=5000,atk=0,defense=100):
    p['entities'].append({'id':key,'kind':'entity','tags':tags,'components':{'attributes':{'base':{'max_hp':hp,'atk':atk,'def':defense,'mres':0,'move_speed':0}},
      'spatial':{},'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},
      'deployable':{'base_cost':0,'capacity':0,'cooldown_seconds':0,'terrain':'both'},'abilities':list(abilities)}})
def interaction():
    p=package('01-12');p['scenarioDraft']={'id':'scenario/m21_peer_interaction','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':11},
      'roster':[],'initialEntities':[{'definition':'unit/chapter01_w','instanceAlias':'w','position':{'row':3,'col':3},
         'components':{'abilities':['ability/chapter01_w_c4_0'],'resources':{'c4_clock_0':{'initial':20}}}}],
      'resources':{'dp':{'initial':99,'capacity':99}},'waves':[],'objectives':{}}
    return p
def retired_registered_attachment_blasts_only_living_member():
    p=interaction();add_actor(p,'unit/peer_focus',['player']);add_actor(p,'unit/peer_neighbor',['player'])
    add_actor(p,'unit/peer_director',['ally'],['ability/activate_focus'],hp=100,defense=0)
    p['abilities'].append({'id':'ability/activate_focus','kind':'ability','activation':{'mode':'manual','on_start':[
      {'op':'activate_predefined','target':'battle','parameters':{'key':'focus-registry'}}]},'timeline':[]})
    p['scenarioDraft']['initialEntities'] += [
      {'definition':'unit/peer_focus','instanceAlias':'focus','registration_key':'focus-registry','active':False,'deployed':True,'position':{'row':3,'col':4}},
      {'definition':'unit/peer_neighbor','instanceAlias':'neighbor','position':{'row':3,'col':5}},
      {'definition':'unit/peer_director','instanceAlias':'director','position':{'row':0,'col':0}}]
    s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/activate_focus'},at=0)
    s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0);s.submit({'action':'withdraw','source':'focus'},at=50)
    s.advance(115);assert not s.ctx.active('focus') and not s.ctx.alive('focus') and s.ctx.resources.current('focus','hp')==5000
    assert s.ctx.resources.current('neighbor','hp')==4254
    areas=[e for e in s.session.events if e['type']=='area.resolved'];assert len(areas)==1 and areas[0]['time']==114
    assert areas[0]['payload']['targets']==[s.session.world.resolve('neighbor')]
    cp(s)
def registered_source_packet_survives_real_retirement():
    p=package('01-12');p['scenarioDraft']={'id':'scenario/registered_source','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':11},
       'roster':[],'resources':{'dp':{'initial':99,'capacity':99}},'waves':[],'objectives':{},'initialEntities':[
       {'definition':'unit/chapter01_w','instanceAlias':'w','registration_key':'w-reg','active':False,'position':{'row':3,'col':3},
          'components':{'abilities':['ability/chapter01_w_normal_0']}}]}
    add_actor(p,'unit/peer_focus',['player']);add_actor(p,'unit/peer_director',['ally'],['ability/activate_w','ability/remove_w'],hp=100,defense=0)
    p['abilities'] += [{'id':'ability/activate_w','kind':'ability','activation':{'mode':'manual','on_start':[
      {'op':'activate_predefined','target':'battle','parameters':{'key':'w-reg'}}]},'timeline':[]},
      {'id':'ability/remove_w','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':2,'parameters':{'reason':'dead'}}]},'timeline':[]}]
    p['scenarioDraft']['initialEntities'] += [{'definition':'unit/peer_focus','instanceAlias':'focus','position':{'row':3,'col':5}},
      {'definition':'unit/peer_director','instanceAlias':'director','position':{'row':0,'col':0}}]
    s=make(p);assert s.session.world.resolve('w')==2;s.submit({'action':'skill','source':'director','ability':'ability/activate_w'},at=0)
    s.submit({'action':'skill','source':'director','ability':'ability/remove_w'},at=10);s.advance(36)
    assert not s.ctx.active('w') and s.ctx.get('w',('runtime','state'))=='dead'
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['time']==21 and hits[0]['payload']['amount']==370
    assert s.ctx.resources.current('focus','hp')==4630;cp(s)
def portal_hidden_attachment_and_terrain_revision():
    p=interaction();p['scenarioDraft']['map']['tiles']=[{'tileKey':'tile_floor','buildableType':1,'passableMask':1} for _ in range(88)]
    p['scenarioDraft']['map']['tiles'][3*11+4]['tileKey']='peer_entry';p['scenarioDraft']['map']['tiles'][3*11+7]['tileKey']='peer_exit'
    p['scenarioDraft']['map']['tile_mechanics']={'peer_entry':{'type':'route_checkpoint_portal','role':'entry'},'peer_exit':{'type':'route_checkpoint_portal','role':'exit'}}
    add_actor(p,'unit/peer_focus',['player']);add_actor(p,'unit/peer_neighbor',['player']);add_actor(p,'unit/peer_director',['ally'],['ability/change_surface'],hp=100,defense=0)
    p['abilities'].append({'id':'ability/change_surface','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_terrain_overlay','target':3,
      'parameters':{'key':'surface','priority':0,'values':{'buildableType':0}}}]},'timeline':[]})
    route={'motionMode':0,'startPosition':{'row':3,'col':4},'endPosition':{'row':3,'col':7},
      'transition_policy':{'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}},
      'checkpoints':[{'type':2,'time':1},{'type':5},{'type':1,'time':5},{'type':6,'position':{'row':3,'col':7}}]}
    p['scenarioDraft']['initialEntities'] += [{'definition':'unit/peer_focus','instanceAlias':'focus','position':{'row':3,'col':4},'route':route},
      {'definition':'unit/peer_neighbor','instanceAlias':'neighbor','position':{'row':3,'col':5}},
      {'definition':'unit/peer_director','instanceAlias':'director','position':{'row':0,'col':0}}]
    s=make(p);assert s.session.world.resolve('focus')==3
    s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0)
    s.submit({'action':'skill','source':'director','ability':'ability/change_surface'},at=50);s.advance(60)
    capture=s.ctx.get('focus',('spatial','portal_capture'));assert s.ctx.route_hidden('focus') and capture['captured_at']==30
    assert s.ctx.get('system/battle',('state','terrain','revision'))==1
    s.advance(55);assert s.ctx.get('focus',('spatial','portal_capture'))==capture
    assert s.ctx.resources.current('focus','hp')==5000 and s.ctx.resources.current('neighbor','hp')==4254
    cp(s)
def untouched_prefix(stage,ticks):
    p=package(stage);initial=deepcopy(p['scenarioDraft']);s=make(p);s.advance(ticks)
    assert p['scenarioDraft']==initial # no native wave/control/actor/route surgery
    events=list(s.session.events);born=[e for e in events if e['type']=='entity.created'];activated=[e for e in events if e['type']=='entity.activated']
    if stage=='01-11':
        ref=s.ctx.state()['predefined_registry']['char_211_adnach'];assert s.ctx.active(ref) and s.ctx.get(ref,('deployable','capacity'))==1
        assert len([e for e in activated if e['payload']['target']==ref])==1
    else:
        assert s.ctx.alive('chapter01/predefined/emp') and s.ctx.spatial.grid.tile(5,5)['buildableType']==0
        assert s.ctx.get('system/battle',('state','terrain','layers'))
        assert not s.ctx.state().get('input_locks')
    assert s.ctx.timeline._state()['phase']!='complete' and not s.ctx.state()['finished']
    cp(s)
    return {'stage':stage,'prefix_ticks':ticks,'entity_created':len(born),'activations':len(activated),'control_statuses':s.ctx.state().get('controls'),
       'timeline':s.ctx.timeline._state(),'pending_tasks':len(s.session.scheduler.pending),'not_full_stage':True}
if __name__=='__main__':
    for stage in PINS:package(stage)
    for path in [Path(__file__),RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json']:
        FILES[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    for p in list(FILES):
        if '/m21/' in p.replace('\\','/') and p.endswith('.json'):
            obj=json.loads(Path(p).read_bytes())
            for source,pin in obj['manifest']['metadata'].get('source_locks',{}).items():
                path=(ROOT/source).resolve()
                if path.is_file():assert hashlib.sha256(path.read_bytes()).hexdigest()==pin;FILES[str(path)]=pin
    start=dict(FILES);cases=[]
    for NAME,fn in [('registered_attachment_retired',retired_registered_attachment_blasts_only_living_member),
      ('registered_source_retired_packet',registered_source_packet_survives_real_retirement),('portal_terrain_projectile',portal_hidden_attachment_and_terrain_revision),
      ('full_01_11_prefix',lambda:untouched_prefix('01-11',150)),('full_01_12_prefix',lambda:untouched_prefix('01-12',150))]:
        LAST=None
        try:result=fn();c={'case':NAME,'result':'passed','summary':result}
        except Exception as error:c={'case':NAME,'result':'failed','error':repr(error)}
        if LAST is not None:
            s=LAST;c.update({'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'commands':s.export_replay(),
              'snapshot':s.snapshot(),'events':[thaw(e) for e in s.session.events]})
        cases.append(c)
    end={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in FILES};stable=start==end and implementation_digest()==CORE
    passed=stable and all(c['result']=='passed' for c in cases)
    (OUT/'report.json').write_bytes((json.dumps({'schema':'ark-sim/m21-cross-peer/v1','passed':passed,'core_start':CORE,'core_end':implementation_digest(),
      'runtime_module':ark_sim.__file__,'source_start':start,'source_end':end,'identity_stable':stable,'fixture_inputs':INPUTS,'cases':cases,
      'formal_approval':False,'review_receipt':False,'scope':'Three isolated interactions and two unchanged stage150tick prefixes; no full chapter approval'},ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'passed':passed,'core':CORE,'cases':[{k:v for k,v in c.items() if k in ('case','result','error')} for c in cases]}))
    raise SystemExit(0 if passed else 1)
