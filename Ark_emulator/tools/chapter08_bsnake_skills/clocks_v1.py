"""Actual empty AlwaysTrigger and two start-relative Ignite cycles."""
import json
from tools.chapter08_bsnake_skills import author_v4_base as base
from tools.chapter08_bsnake_skills.build_v1 import BASE,CORE,TIMER,sha
from tools.chapter08_bsnake_skills.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
OUT=BASE/'skills_clocks_v1'
def run(kind):
    p=base.package(0,kind)
    if kind=='explode':p['entities'][1]['components'].pop('buffs',None)
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=818)
    start=1065 if kind=='explode' else 1145;end=2150 if kind=='explode' else 1250
    folder=OUT/kind;folder.mkdir(parents=True,exist_ok=True);s.session.advance(start);cp=folder/'checkpoint.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h),providers=reg);s.session.advance(end-start);r.session.advance(end-start);head=replay(s.program,s.export_replay(),providers=reg)
    assert base.domain(s)==base.domain(r)==base.domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
    starts=[(e['time'],list(e['payload']['targets'])) for e in s.session.events if e['type']=='ability.started']
    applied=[(e['time'],e['payload']['target']) for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==TIMER]
    if kind=='explode':assert starts==[(1050,[]),(2100,[])] and applied==[]
    else:assert starts==[(570,[3,4]),(1140,[5,6])] and applied==[(605,3),(605,4),(1175,5),(1175,6)]
    (folder/'input.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(folder/'replay.json').write_text(json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with (folder/'events.jsonl').open('wb') as f:
        for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False)+'\n').encode())
    return {'case':kind,'starts':starts,'applied':applied,'CP':True,'head':True,'all_events':True,'files':{str(x):sha(x) for x in folder.iterdir()}}
def main():
    assert implementation_digest()==CORE;OUT.mkdir(exist_ok=True);rows=[run(x) for x in ('explode','ignite')];out=OUT/'report.json';assert not out.exists();out.write_text(json.dumps({'status':'two_clocks_passed','core':CORE,'module_sha256':sha(BASE/'skills.module.v4.json'),'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(sha(out))
if __name__=='__main__':main()
