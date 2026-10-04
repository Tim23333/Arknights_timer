"""Reuse independently frozen public counter-inputs with new talent content."""
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter06_npcs.huang_v6_policy import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    source=ROOT/'validation/campaign/chapter06_selfremove_huang_independent/inputs.json'
    talent=ROOT/'packages/campaign/chapter06_npcs/huang_talents.v7.model.json'
    old=json.loads(source.read_bytes());new=json.loads(talent.read_bytes())
    out=ROOT/'validation/campaign/chapter06_npc_huang_v7_guarded';out.mkdir(exist_ok=False)
    files=[source,talent,Path(__file__),ROOT/'tools/chapter06_npcs/huang_v6_policy.py',ROOT/'tools/chapter06_npcs/policies.py']
    before={str(p):sha(p) for p in files};rows=[]
    for idx,(data,expected) in enumerate(zip(old,[1153.5,2352.5,1])):
        p=deepcopy(data)
        for key in ('rules','buffs','selectors'):
            replacements={d['id']:d for d in new.get(key,[])}
            p[key]=[d for d in p.get(key,[]) if d['id'] not in replacements]+list(replacements.values())
        folder=out/str(idx);folder.mkdir();(folder/'input.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf8')
        reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),seed=6471,providers=reg)
        s.submit({'action':'skill','source':'dealer','ability':'ability/peer/hit'},at=10)
        s.advance(9);cp=folder/'before_damage.checkpoint.json';pin=write_ordered(cp,s.checkpoint())
        restored=Engine.restore(s.program,load_bound(cp,pin),providers=reg)
        for sim in (s,restored):sim.advance(3)
        actual=s.ctx.resources.current('native_npc','hp')
        (folder/'observed.json').write_text(json.dumps({'expected':expected,'actual':actual,'events':thaw(tuple(s.session.events))},indent=2)+'\n',encoding='utf8')
        assert actual==expected,(idx,actual,expected)
        assert not any(b['definition']=='buff/ch6/npc/huang_once' for b in s.ctx.get('native_npc',('buffs','instances')))
        head=replay(s.program,s.export_replay(),providers=reg)
        assert s.checkpoint()==restored.checkpoint()==head.checkpoint()
        rows.append({'index':idx,'expected_hp':expected,'actual_hp':actual,'passed':True,'checkpoint_sha':pin,'head_and_restore_equal':True})
    after={str(p):sha(p) for p in files};assert before==after
    report={'passed':True,'core':implementation_digest(),'guards_start':before,'guards_end':after,'cases':rows,
        'scope':'Original independent base/dynamic-capacity/Buff-heal-free public inputs and unchanged expected HP; content reaction ordering explicit reference policy'}
    target=out/'verification.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':sha(target)}))


if __name__=='__main__':main()
