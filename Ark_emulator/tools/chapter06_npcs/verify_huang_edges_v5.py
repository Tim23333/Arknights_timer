"""True maxHP changes, heal-free and native15s resistance boundary."""
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter06_npcs.policies import providers


def make(p):return Engine.create(Compiler(providers=providers()).compile(p),seed=61720,providers=providers())


def main():
    base=ROOT/'validation/campaign/chapter06_npc_huang_talents_v5/input.json';data=json.loads(base.read_bytes())
    out=ROOT/'validation/campaign/chapter06_npc_huang_edges_v5';assert not out.exists();out.mkdir(parents=True);cases=[]
    p=deepcopy(data);p['entities'][0]['components']['resources']['hp'].pop('capacity');p['entities'][0]['components']['resources']['hp']['capacity_attribute']='max_hp'
    p['buffs'].append({'id':'buff/npc_probe/maxhp','kind':'buff','modifiers':[{'attribute':'max_hp','layer':'flat','value':1000}]})
    p['scenarioDraft']['scheduledEffects']=[{'at':1,'effect':{'op':'apply_buff','target':2,'buff':'buff/npc_probe/maxhp'}}]
    s=make(p);s.submit({'action':'skill','source':'attacker','ability':'ability/npc_probe/hit'},at=10);s.submit({'action':'skill','source':'attacker','ability':'ability/npc_probe/hit'},at=20)
    s.session.advance(12);assert s.ctx.resources.current('huang','hp')==1653.5
    s.session.advance(10);assert s.ctx.resources.current('huang','hp')==1652.5
    assert s.checkpoint()==replay(s.program,s.export_replay(),providers=providers()).checkpoint();cases.append({'case':'maxHP3305 heal1652.5 and floor1652.5','passed':True})
    p=deepcopy(data);p['entities'][0]['components']['selection_state']['heal_free']=True;s=make(p)
    s.submit({'action':'skill','source':'attacker','ability':'ability/npc_probe/hit'},at=10);s.session.advance(12)
    assert s.ctx.resources.current('huang','hp')==1 and not [e for e in s.session.events if e['type']=='healing.accepted']
    assert not any(b['definition']=='buff/ch6/npc/huang_once' for b in s.ctx.get('huang',('buffs','instances')))
    assert s.checkpoint()==replay(s.program,s.export_replay(),providers=providers()).checkpoint();cases.append({'case':'heal-free blocks heal but once talent consumed and lock installed','passed':True})
    s=make(data);s.session.advance(450)
    assert not any(b['definition']=='buff/ch6/npc/huang_resistance' for b in s.ctx.get('huang',('buffs','instances')))
    s.session.advance(1);assert sum(b['definition']=='buff/ch6/npc/huang_resistance' for b in s.ctx.get('huang',('buffs','instances')))==1
    s.session.advance(451);assert sum(b['definition']=='buff/ch6/npc/huang_resistance' for b in s.ctx.get('huang',('buffs','instances')))==1
    assert s.checkpoint()==replay(s.program,s.export_replay(),providers=providers()).checkpoint();cases.append({'case':'native15s initial wait then one resistance buff only','passed':True})
    p=out/'verification.json';p.write_text(json.dumps({'passed':True,'core':implementation_digest(),'cases':cases,
        'scope':'Author dynamicMaxHP/heal-free/once/15s first trigger; independent native talent semantics/whole-stage pending'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(p.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
