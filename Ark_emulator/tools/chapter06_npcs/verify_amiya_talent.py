"""Source talent only with an explicit test SP store; native NPC stays no-skill."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter06_npcs.amiya_policy import providers


def main():
    base=ROOT/'validation/campaign/chapter06_npc_amiya_v1/input.json';p=json.loads(base.read_bytes());npc=next(e for e in p['entities'] if e['id']=='unit/ch6/npc/char_002_amiya')
    npc['components']['resources']['sp']={'initial':0,'capacity':100}
    target=next(e for e in p['entities'] if e['id']=='unit/npc_probe/amiya_target')
    out=ROOT/'validation/campaign/chapter06_npc_amiya_talent_v1';assert not out.exists();out.mkdir(parents=True)
    cases=[]
    for name,hp,expected in [('surviving_hit',10000,2),('lethal_hit',100,8)]:
        data=deepcopy(p);victim=next(e for e in data['entities'] if e['id']=='unit/npc_probe/amiya_target');victim['components']['resources']['hp']['initial']=hp
        reg=providers();s=Engine.create(Compiler(providers=reg).compile(data),seed=61724,providers=reg)
        s.submit({'action':'skill','source':'controller','ability':'ability/npc_probe/activate_amiya'},at=5);s.session.advance(45)
        ref=s.ctx.state()['predefined_registry']['char_002_amiya'];assert s.ctx.resources.current(ref,'sp')==expected,(name,s.ctx.resources.current(ref,'sp'))
        assert s.checkpoint()==replay(s.program,s.export_replay(),providers=reg).checkpoint()
        cases.append({'case':name,'actual_sp':expected,'source_no_additional_damage':len([e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==ref])==1,'head_equal':True})
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'cases':cases,
        'scope':'Explicit controlled SP resource used solely to test source attack2/kill8 talent. Native no-selected-skill NPC module has no SP; no global roster replacement.'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
