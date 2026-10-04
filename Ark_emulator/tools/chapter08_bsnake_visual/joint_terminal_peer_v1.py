"""Fresh82 finite terminalHP0 membership; no migrated4bf author result."""
import json
from tools.chapter08_bsnake_visual.joint_peer_v1 import package,providers,domain,members,ROOT,BASE,CORE,BOSS,STAGE,sha
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter08_visual_joint_terminal_independent_v1'
def main():
    assert implementation_digest()==CORE;OUT.mkdir(exist_ok=True);p=package();ctrl=next(d for d in p['definitions'] if d['id']=='unit/peer82/controller')
    for name,effect in [('down',{'op':'instant_kill','parameters':{'cause':'peer82_visual_lifecycle','skip_rebirth':False}}),('detach_screen',{'op':'remove_buff','buff':'buff/ch8/source/bsnake_s[screen_attack]'})]:
        aid='ability/peer82/'+name;ctrl['components']['abilities'].append(aid);p['definitions'].append({'id':aid,'kind':'ability','selector':'selector/peer82/boss','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':effect}]})
    p['scenarioDraft']['commands']=[{'at':t,'action':'skill','source':'controller','ability':'ability/peer82/'+name} for t,name in ((3,'down'),(181,'detach_screen'),(184,'down'))]
    p['manifest']['metadata']['peer_fixture']+=' Explicitpublic controlled firstscreen detach181 before second184 life trigger isolates visuals; native28 definition/stats unchanged, not fullphase timing proof.'
    s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=887);seen=[]
    for t in (4,154,185,200):
        s.session.advance(t-s.session.time);seen.append({'time':t,'HP':s.ctx.resources.current('boss','hp'),'active':s.ctx.active('boss'),'mode':s.ctx.resources.current('boss','mode'),'members':members(s)})
    cp=OUT/'checkpoint_waiting200.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=providers());s.session.advance(138);r.session.advance(138);head=replay(s.program,s.export_replay(),providers=providers());assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
    final={'time':s.session.time,'HP':s.ctx.resources.current('boss','hp'),'active':s.ctx.active('boss'),'mode':s.ctx.resources.current('boss','mode'),'members':members(s)}
    assert final=={'time':338,'HP':0,'active':True,'mode':3,'members':['air','plain','untargetable']},final
    assert next(x for x in seen if x['time']==154)['HP']==75000 and next(x for x in seen if x['time']==154)['members']==['air','plain','untargetable']
    assert all(s.ctx.resources.current(name,'hp')==3777 for name in ('plain','air','untargetable','concealed','hostile','othercategory'))
    (OUT/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(OUT/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
    with (OUT/'events.jsonl').open('wb') as f:
        for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False)+'\n').encode())
    out=OUT/'report.json';assert not out.exists();out.write_bytes((json.dumps({'status':'fresh82_original_source_terminal_HP0_membership_CP_head_passed','core':CORE,'Boss_sha256':sha(BOSS),'stage_sha256':sha(STAGE),'seen':seen,'final':final,'CP200_to338':True,'head':True,'all_events':True,'scope':'Actualjoined82HP0terminal and originalalive source actor, sourcevisualmembers only; explicitearlydetach fixture doesnot verify28phase/firechallenge.'},ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()
