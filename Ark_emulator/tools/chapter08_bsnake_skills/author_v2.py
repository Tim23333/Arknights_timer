"""Independent source numeric fixtures; CP and replay full event domain."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_chapter08_joint_v4_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.chapter08_bsnake_skills.build_v1 import CORE,BASE,FIRE,OWNER,sha,TIMER,CHILD,MARKER
from tools.chapter08_bsnake_skills.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=BASE/'skills_author_v2'
def package(mode=0,kind='ignite'):
    p=json.loads((BASE/'skills.module.v3.json').read_bytes());burn=json.loads(FIRE.read_bytes())
    for key in ('rules','buffs'):p[key]+=burn[key]
    abilities=p['manifest']['metadata']['owned_ability_bindings'];aid='ability/ch8/bsnake/'+kind+'/phase'+str(mode)
    p['entities']=[{'id':OWNER,'kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':50000,'atk':770,'def':800,'mres':50,'attack_speed_ratio':1}},'resources':{'hp':{'initial':50000,'capacity':50000,'role':'health'},'mode':{'initial':mode,'capacity':3}},'spatial':{},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'abilities':[aid],'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
    p['scenarioDraft']={'id':'scene/bsnake/skills/'+kind+'/'+str(mode),'ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':7},'initialEntities':[{'definition':OWNER,'instanceAlias':'boss','position':{'row':3,'col':1}}]}
    for name,row,col,res,taunt in [('primary',3,3,20,10),('adjacent',3,4,40,5),('other',2,3,60,1),('outside',4,4,0,0)]:
        id='unit/fixture/'+name;components={'attributes':{'base':{'max_hp':30000,'atk':0,'def':999,'mres':res,'taunt_level':taunt,'one_minus_status_resistance':1}},'resources':{'hp':{'initial':30000,'capacity':30000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'}}
        if kind=='explode' and name=='primary':components['buffs']={'initial':[TIMER,CHILD]}
        p['entities'].append({'id':id,'kind':'entity','tags':['player'],'components':components});p['scenarioDraft']['initialEntities'].append({'definition':id,'instanceAlias':name,'position':{'row':row,'col':col}})
    p['manifest']['metadata']['fixture']='Native Boss base fields preserved; target fixtures only, no normal consumer/phase/rebirth/stage claim. Skill selected independently to isolate source clock.'
    return p
def domain(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def run(mode,kind):
    p=package(mode,kind);reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=8108)
    folder=OUT/(kind+'_'+str(mode));folder.mkdir(parents=True,exist_ok=True);start=600 if kind=='ignite' else 1065;end=670 if kind=='ignite' else 1130
    s.session.advance(start);cp=folder/'checkpoint.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.session.advance(end-start);r.session.advance(end-start);head=replay(program,s.export_replay(),providers=reg)
    assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
    relevant=[e for e in s.session.events if e['type'] in ('ability.started','damage.accepted','buff.applied','buff.removed','area.resolved')]
    (folder/'input.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (folder/'replay.json').write_text(json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with (folder/'events.jsonl').open('wb') as f:
        for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False)+'\n').encode())
    print(json.dumps({'mode':mode,'kind':kind,'events':[thaw(e) for e in relevant]},ensure_ascii=False))
    return {'mode':mode,'kind':kind,'CP':True,'head':True,'full_event_equality':True,'observations':[thaw(e) for e in relevant],'files':{str(x):sha(x) for x in folder.iterdir()}}
def main():
    assert implementation_digest()==CORE;OUT.mkdir(exist_ok=True);rows=[run(m,k) for m in (0,1) for k in ('ignite','explode')]
    out=OUT/'observations.json';assert not out.exists();out.write_text(json.dumps({'core':CORE,'rows':rows,'numeric_assertions_pending':True},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(sha(out))
if __name__=='__main__':main()
