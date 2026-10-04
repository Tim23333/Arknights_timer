"""Independent joined111def Boss/346def stage source membership, fresh82 identity."""
import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_joint_v4.build_bsnake_partial_join_v1 import providers as baseline
from tools.chapter08_flame_device.policies_v1 import providers as flame
BASE=ROOT/'packages/campaign/chapter08_consumers/bsnake';BOSS=BASE/'four_modes.visual_source.v6.json';STAGE=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v4.json';OUT=ROOT/'validation/campaign/chapter08_visual_joint_independent_v1';CORE='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae';OWNER='unit/ch8/bsnake/cadb87696bef4de2';CHILD='buff/ch8/source/bsnake_s[screen_attack][effect]'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exact(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b
def providers():return {**baseline(),**flame()}
def audit():
    assert sha(BOSS)=='d5c259d1698d43c4362f0efb86f0a7e12de283b0be24b9c96320c42f10bc882a' and sha(STAGE)=='fdfa0bca0f6034602d1f69630b8727db74c864c226e4de3c17ea3150fae1860a'
    b=json.loads(BOSS.read_bytes());s=json.loads(STAGE.read_bytes());old=json.loads((STAGE.parent/'level_main_08-17.native_draft.v3.json').read_bytes());d={v['id']:v for v in s['definitions']};prior={v['id']:v for v in old['definitions']}
    assert len(d)==len(s['definitions'])==346 and len(b['definitions'])==111
    assert exact(s['scenarioDraft'],old['scenarioDraft']) and len(s['scenarioDraft']['timeline']['waves'])==4
    assert sum(a.get('count',1) for w in s['scenarioDraft']['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn')==44
    for ident,v in prior.items():
        if ident!=OWNER:assert exact(v,d[ident]),ident
    for v in b['definitions']:assert exact(v,d[v['id']]),v['id']
    source=json.loads((BASE/'four_modes.wave_source.v5.json').read_bytes());original=next(v for v in source['definitions'] if v['id']==OWNER)['components'];current=d[OWNER]['components']
    assert current['abilities']==original['abilities'] and exact(current['attributes'],original['attributes']) and exact(current['resources'],original['resources']) and exact(current['selection_state'],original['selection_state'])
    return {'335_existing_nonBoss_defs_type_exact':True,'scenario_including_routes_map_controls_loop_predefines_roster_same':True,'spawn44_waves4':True,'Boss_owned10_and_stats_original':True,'new_visual_defs10':len(set(d)-set(prior)),'Boss_sha256':sha(BOSS),'stage_sha256':sha(STAGE)}
def package():
    p=json.loads(BOSS.read_bytes());known={v['id']:v for v in p['definitions']};f=json.loads((BASE.parent/'flame/module.v4.joint.json').read_bytes())
    for key in ('entities','buffs','rules','selectors','projectiles','abilities'):
        for value in f.get(key,[]):
            if value['id'] in known:assert exact(value,known[value['id']])
            else:p['definitions'].append(value);known[value['id']]=value
    choices=[('plain',0,1,1,{}),('air',0,2,1,{}),('untargetable',0,1,1,{'target_free':True}),('concealed',0,1,1,{'camouflage':True}),('hostile',1,1,1,{}),('othercategory',0,1,2,{})]
    for name,side,motion,category,extra in choices:p['definitions'].append({'id':'unit/peer82/'+name,'kind':'entity','tags':[name],'components':{'attributes':{'base':{'max_hp':3777,'atk':0,'def':712,'mres':23}},'resources':{'hp':{'initial':3777,'capacity':3777,'role':'health'}},'spatial':{},'selection_state':{'side':side,'motion':motion,'category':category,'unit_type':1,**extra},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    actions=[('to2',{'op':'modify_resource','resource':'mode','value':2}),('to1',{'op':'modify_resource','resource':'mode','value':1}),('to3',{'op':'modify_resource','resource':'mode','value':3}),('retire',{'op':'retire','parameters':{'reason':'withdrawn'}})]
    p['definitions'].append({'id':'selector/peer82/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}]})
    for name,e in actions:p['definitions'].append({'id':'ability/peer82/'+name,'kind':'ability','selector':'selector/peer82/boss','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':e}]})
    p['definitions'].append({'id':'unit/peer82/controller','kind':'entity','components':{'attributes':{'base':{'max_hp':921,'atk':0,'def':0,'mres':0}},'resources':{'hp':{'initial':921,'capacity':921,'role':'health'}},'spatial':{},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':1},'abilities':['ability/peer82/'+name for name,e in actions],'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    loop=json.loads((BASE.parent/'flame/loop.profile.v3.json').read_bytes());p['scenarioDraft']={'id':'scene/independent82/visual_members','ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':15},'branches':loop['runtime_branch'],'initialEntities':deepcopy(loop['initial_entities'])+[{'definition':'unit/peer82/controller','instanceAlias':'controller','position':{'row':8,'col':0}}]+[{'definition':'unit/peer82/'+name,'instanceAlias':name,'position':{'row':8,'col':i+2}} for i,(name,*rest) in enumerate(choices)],
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','delay_seconds':1/30,'count':1,'managed':True,'blocks_wave':True,'spawn':{'definition':OWNER,'instanceAlias':'boss','position':{'row':4,'col':11}}}]}]},{'fragments':[{'actions':[]}]}]},
        'commands':[{'at':t,'action':'skill','source':'controller','ability':'ability/peer82/'+name} for t,name in ((4,'to2'),(9,'to1'),(13,'to3'),(19,'retire'))]}
    p['manifest']['metadata']['peer_fixture']='Independent newtargets3777/712/23 and positions/publictimes, no authorfixture reuse; sourceV6actor unchanged, publicmodeprojection not nativephase timing proof.'
    return p
def members(s):return sorted(name for name in ('plain','air','untargetable','concealed','hostile','othercategory','boss') if any(i['definition']==CHILD for i in s.ctx.entity(name)['components'].get('buffs',{}).get('instances',[])))
def domain(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def main():
    assert implementation_digest()==CORE;OUT.mkdir(exist_ok=True);a=audit();p=package();s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=851);observations=[]
    for t in (2,5,10,14):s.session.advance(t-s.session.time);observations.append({'time':t,'members':members(s)})
    assert [v['members'] for v in observations]==[[],['air','plain','untargetable'],[],['air','plain','untargetable']]
    cp=OUT/'checkpoint14.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=providers());s.session.advance(9);r.session.advance(9);h=replay(s.program,s.export_replay(),providers=providers());assert domain(s)==domain(r)==domain(h) and tuple(s.session.events)==tuple(r.session.events)==tuple(h.session.events)
    assert members(s)==[] and not s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==50000
    assert all(s.ctx.resources.current(name,'hp')==3777 for name in ('plain','air','untargetable','concealed','hostile','othercategory'))
    (OUT/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(OUT/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
    with (OUT/'events.jsonl').open('wb') as f:
        for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False)+'\n').encode())
    out=OUT/'report.json';assert not out.exists();out.write_bytes((json.dumps({'status':'fresh82_joint_membership_sourcefield_CP_head_passed','core':CORE,'audit':a,'observations':observations,'retire_cleared':True,'targetHP_unchanged':True,'CP14_to23':True,'head':True,'all_events':True,'scope':'JoinedV6visual and stageV4static sourcefields only; no author4bf proof migration/no nativephase timing or gameplaywhole approval.'},ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()
