"""Independent public Cold/Frozen boundary probe; no author test fixture import."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v5_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

CORE='0fe88573f05b279aa3873ce5c2babaecce5e208cec8b1c7172052c3d1780b163'
COLD='buff/ch6/cold/e2c_cold';FROZEN='buff/ch6/cold/e2c_freeze'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def package(immune=()):
    path=ROOT/'packages/campaign/chapter06_cold/model.json'
    assert sha(path)=='e610f9446b077c6df7a86922e6719226e5a352a3826d6fe40c49e3296437b4dc'
    p=json.loads(path.read_bytes())
    actors=[]
    for index,alias in enumerate(['first','second','receiver']):
        target=alias=='receiver'
        components={'attributes':{'base':{'max_hp':9000,'atk':100,'def':13,'mres':0,
            'attack_speed_ratio':1,'attack_interval':3,'move_speed':1,'one_minus_status_resistance':.4}},
            'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'},
                         'sp':{'initial':0,'capacity':100,'recovery_rate':1,'recovery_freeze_rule':'rule/ch6/cold/frozen_recovery'}},
            'spatial':{},'selection_state':{'side':0 if target else 1,'motion':1,'category':1,'unit_type':1,'abnormal_immunes':list(immune) if target else []},
            'lifecycle':{'policy':'policy/ark_lifecycle'},
            'abilities':[] if target else ['ability/ch6/cold/apply5','ability/ch6/cold/apply10','ability/root/hit']}
        if alias=='first':components['buffs']={'initial':['buff/ch6/cold/frozen_atkscale2.5']}
        p.setdefault('entities',[]).append({'id':'unit/root/'+alias,'kind':'entity','tags':['player','cold_receiver'] if target else ['enemy'], 'components':components})
        actors.append({'definition':'unit/root/'+alias,'instanceAlias':alias,'position':{'row':0,'col':index}})
    p['abilities'].append({'id':'ability/root/hit','kind':'ability','activation':{'mode':'manual'},
                          'selector':'selector/ch6/cold/receiver','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical','scale':1}}]})
    p['scenarioDraft']={'id':'scene/root/cold','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},'objectives':{},'initialEntities':actors}
    return p


def main():
    assert implementation_digest()==CORE
    out=ROOT/'validation/campaign/root_cold_joint_probe_v1';assert not out.exists();out.mkdir(parents=True)
    reg=providers();p=package();program=Compiler(providers=reg).compile(p);s=Engine.create(program,seed=641,providers=reg)
    # First hit sees no Frozen (100-13=87); second Cold from another source turns into 2-second Frozen.
    cmds=[(0,'first','ability/root/hit'),(2,'first','ability/ch6/cold/apply10'),
          (25,'second','ability/ch6/cold/apply5'),(27,'first','ability/root/hit')]
    for at,source,ability in cmds:s.submit({'action':'skill','source':source,'ability':ability},at=at)
    s.session.advance(3)
    assert s.ctx.get('receiver',('attributes','base','attack_speed_ratio')) == 1
    cold=[i for i in s.ctx.get('receiver',('buffs','instances'),[]) if i['definition']==COLD]
    assert len(cold)==1 and cold[0]['expires_at']==122
    s.session.advance(23)
    frozen=[i for i in s.ctx.get('receiver',('buffs','instances'),[]) if i['definition']==FROZEN]
    assert len(frozen)==1 and frozen[0]['expires_at']==85
    assert not [i for i in s.ctx.get('receiver',('buffs','instances'),[]) if i['definition']==COLD]
    assert frozen[0]['source']==s.session.world.resolve('second')
    sp=s.ctx.resources.current('receiver','sp')
    cp=out/'ordered.checkpoint.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=reg)
    for sim in (s,restored):sim.session.advance(59)
    assert s.ctx.resources.current('receiver','sp')==sp
    # Exact half-open boundary: Frozen expires at85, first resumed recovery is the tick85 system.
    for sim in (s,restored):sim.session.advance(1)
    assert s.ctx.resources.current('receiver','sp')>sp
    assert not [i for i in s.ctx.get('receiver',('buffs','instances'),[]) if i['definition']==FROZEN]
    hits=[e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']
    assert hits==[87,237],hits
    head=replay(program,s.export_replay(),providers=reg)
    assert s.checkpoint()==restored.checkpoint()==head.checkpoint()
    # Cold immunity is a pure rejection/no-op, including event and random state.
    immune=Engine.create(Compiler(providers=reg).compile(package([23])),seed=641,providers=reg)
    before=immune.checkpoint()
    immune.ctx.effects.execute('first',['receiver'],{'op':'buff_application','application_rule':'rule/ch6/cold/application',
        'allowed':[COLD,FROZEN],'parameters':{'duration_seconds':5}})
    assert immune.checkpoint()==before
    assert implementation_digest()==CORE
    target=out/'verification.json'
    target.write_text(json.dumps({'passed':True,'core':CORE,'module_sha':sha(ROOT/'packages/campaign/chapter06_cold/model.json'),
        'provider_sha':sha(ROOT/'tools/chapter06/cold/policies.py'),'actual_damage':hits,'cold_expires':122,'frozen_expires':85,
        'disk_sha':pin,'checkpoint_equal':True,'head_replay_equal':True,'immune_noop_exact':True,
        'scope':'Root fresh actors/source values and half-open boundaries; reference duration policy, no whole chapter6/client approval'},indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'passed':True,'sha':sha(target)}))


if __name__=='__main__':main()
