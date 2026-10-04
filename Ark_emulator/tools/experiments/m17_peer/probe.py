"""Independent projectile endpoints; canonical W definitions stay unchanged."""
import sys
from pathlib import Path
import json
import hashlib
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m17_projectile_candidate'
CORE='b964bef82bbc9f6a05cad76740e81030dc9b3d72e82641c3b809d65fb2df875e'
PACKAGE=ROOT/'packages/campaign/chapter01_models/projectile_lifecycle/model.json'
PIN='8d416e8c72e1b3524f5bd6201b6216b42a5d14d9bba4129433c73b9ed58f2c44'
sys.path.insert(0,str(RUNTIME))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
sys.path.append(str(ROOT))
from tools.build_chapter01_w_combat import fixture
LAST=None;LOADED={}
def read(path,pin=None):
    raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if pin:assert sha==pin
    LOADED[str(path)]=sha;return json.loads(raw)
def scene():
    p=fixture(read(PACKAGE,PIN),positions=((3,4),(3,5)))
    unit=p['entities'][0];unit['components']['abilities']=[a for a in unit['components']['abilities'] if not a.startswith('ability/chapter01_w_normal_')]
    unit['components']['resources']['c4_clock_0']['initial']=20
    return p
def make(p):
    global LAST
    LAST=Engine.create(Compiler().compile(p),seed=1717);return LAST
def roundtrip(s):
    r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def hidden_C4_retains_point_hits_visible_neighbor():
    p=scene();route={'motionMode':0,'startPosition':{'row':3,'col':4},'endPosition':{'row':3,'col':4},
      'transition_policy':{'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}},
      'checkpoints':[{'type':2,'time':1},{'type':5},{'type':1,'time':10},{'type':6,'position':{'row':3,'col':4}}]}
    p['scenarioDraft']['initialEntities'][1]['route']=route
    s=make(p);s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0)
    s.advance(31);assert s.ctx.route_hidden('target0') and len([e for e in s.session.events if e['type']=='projectile.launched'])==1
    s.advance(84)
    expected=470*1.8-100 # pinned native W ATK470/scale1.8; fixture DEF100
    actual={'visible_neighbor_HP':s.ctx.resources.current('target1','hp'),'hidden_target_HP':s.ctx.resources.current('target0','hp'),
      'area_events':[thaw(e) for e in s.session.events if e['type']=='area.resolved']}
    assert actual['visible_neighbor_HP']==5000-expected and actual['hidden_target_HP']==5000,repr(actual)
    roundtrip(s)
def C4_actual_hit_time_ATK_and_metadata_boundary():
    p=scene();p['buffs'].append({'id':'buff/peer_atk','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':100}]})
    p['entities'][0]['components']['abilities'].append('ability/peer_buff')
    p['abilities'].append({'id':'ability/peer_buff','kind':'ability','activation':{'mode':'manual','on_start':[
      {'op':'apply_buff','target':'source','buff':'buff/peer_atk'}]},'timeline':[]})
    s=make(p);s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0)
    s.submit({'action':'skill','source':'w','ability':'ability/peer_buff'},at=50);s.advance(115)
    assert all(e['payload']['amount']==(470+100)*1.8-100 for e in s.session.events if e['type']=='damage.accepted')
    assert s.ctx.resources.current('target1','hp')==5000-926
    roundtrip(s)
if __name__=='__main__':
    start=implementation_digest();cases=[]
    for name,fn in [('hidden_C4_visible_neighbor',hidden_C4_retains_point_hits_visible_neighbor),('C4_hit_time_stats',C4_actual_hit_time_ATK_and_metadata_boundary)]:
        LAST=None
        try:fn();c={'case':name,'result':'passed'}
        except Exception as e:c={'case':name,'result':'failed','error':repr(e)}
        if LAST is not None:
            s=LAST;c.update({'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'initial_scenario':thaw(s.program.scenario),
                'commands':s.export_replay(),'snapshot':s.snapshot(),'events':[thaw(e) for e in s.session.events]})
        cases.append(c)
    out=ROOT/'validation/campaign/m17_peer_initial.json';out.write_text(json.dumps({'core_start':start,'core_completion':implementation_digest(),
      'runtime_module':ark_sim.__file__,'actual_files_before_decode':LOADED,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'formal_approval':False,'cases':cases},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'core':start,'cases':[{k:v for k,v in c.items() if k in ('case','result','error')} for c in cases]}))
