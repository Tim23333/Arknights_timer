"""Independent literal join audit and source-bound controlled first transition."""
import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_chapter08_joint_v4_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_bsnake_combat.policies_v1 import providers as combat
from tools.chapter08_bsnake_skills.policies_v1 import providers as skills
from tools.chapter08_bsnake.screen_policy_v1 import providers as screen
from tools.chapter08_joint_v4.build_summon_hint_v2 import providers as hint
CORE='20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30'
BASE=ROOT/'packages/campaign/chapter08_consumers/bsnake';JOIN=BASE/'partial_join.module.v1.json';PLAN=ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json'
OUT=ROOT/'validation/campaign/chapter08_join_review_v1';OWNER='unit/ch8/bsnake/cadb87696bef4de2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def providers():return {**combat(),**skills(),**screen(),**hint()}
def same(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b
def audit():
    assert sha(JOIN)=='6b281d44baae413228277562e7b0fb91078690ba2b20092c9a32d942aa8e24b5'
    p=json.loads(JOIN.read_bytes());defs=p['definitions'];ids=[x['id'] for x in defs];assert len(ids)==len(set(ids))==80
    d={x['id']:x for x in defs};owner=d[OWNER]['components'];entries=owner['ability_arbitration']['entries']
    assert len(owner['abilities'])==len(set(owner['abilities']))==10
    assert [e['ability'] for e in entries]==owner['abilities'] and all(type(e['priority']) is int and type(e['attack_clock']) is bool and type(e['require_attack_control']) is bool for e in entries)
    parent_names=['combat.module.v2.json','skills.module.v4.json','first_screen.module.v2.json','summon_hint.module.v4.json'];parent_paths=[BASE/x for x in parent_names]+[BASE.parent/'boss/dragon_fire.module.v12.joint.json']
    changed=[];allowed={OWNER,'behavior/ch8/bsnake/normal','behavior/ch8/bsnake/firstscreen','buff/ch8/source/bsnake_s[screen_attack]'}
    for path in parent_paths:
        q=json.loads(path.read_bytes())
        for key,values in q.items():
            if key not in ('entities','abilities','buffs','behaviors','rules','projectiles','selectors'):continue
            for v in values:
                if v['id'] in allowed:
                    if v['id'] not in d or not same(v,d[v['id']]):changed.append({'parent':path.name,'id':v['id']})
                else:assert v['id'] in d and same(v,d[v['id']]),(path,v['id'])
    for a in d.values():
        if a['kind']=='ability' and a['id'].startswith('ability/ch8/bsnake/normal/'):
            assert a['duration_seconds']==2.3333332538604736 and a['rules']['ability.duration']=='rule/ch8/bsnake/normal/duration'
        if a['kind']=='ability' and '/phase' in a['id'] and a['id'].startswith('ability/ch8/bsnake/'):
            assert 'inputs.resources.mode.current == ' in a['activation']['condition']
    on_begin=owner['rebirth']['on_begin'];assert on_begin[0]=={'op':'remove_buff','target':'source','buff':'buff/ch8/source/bsnake_t[protect]'}
    assert on_begin[-1]=={'op':'apply_buff','target':'source','buff':'buff/ch8/source/bsnake_t[protect]/reborn'}
    restart=next(e for e in d['buff/ch8/source/bsnake_s[screen_attack]']['on_remove'] if e['op']=='restart_behavior')
    clocks=restart['parameters']['initial_cooldowns'];assert clocks=={'ability/ch8/bsnake/ignite/phase1':19.0,'ability/ch8/bsnake/explode/phase1':35.0,'ability/ch8/bsnake/summon_flame':75}
    native=json.loads(PLAN.read_bytes())['stages']['level_main_08-17']['native_document'];rows=len(native['mapData']['map']);cols=len(native['mapData']['map'][0]);assert (rows,cols)==(9,15)
    closure=json.loads((BASE/'source.closure.v1.json').read_bytes());raw=next(c['raw'] for c in closure['prefab']['components'].values() if c['native_class']=='BsnakeScreenAttack');peel=raw['_borderToPeel'];assert type(peel) is int and peel==1
    actual_rows=sorted({x['motion']['parameters']['row'] for x in defs if x['kind']=='projectile' and x['id'].startswith('projectile/ch8/bsnake/firecommon/')})
    assert actual_rows==[1,2,3]
    return {'join_sha256':sha(JOIN),'unique_definitions':80,'owned_and_arbitrated_abilities':10,'permitted_join_changes':changed,'exact_unchanged_other_definitions':True,
        'phase1_restart_initial_seconds':clocks,'clock_policy':'Current explicit restart policy resets full19/35/75 from firstscreen finish. This is stronger than retaining absolute born timers or pausing33seconds; raw SwitchMode restartFSM=true has no recovered method body proving which initial-clock policy. Actual policy will be measured, not labelled native pause proof.',
        'map':{'rows':rows,'cols':cols,'source_peel':peel,'required_rows':list(range(peel,rows-peel)),'controlled_rows':actual_rows,'required_projectile_prototypes':(rows-2*peel)*4,'controlled_projectile_prototypes':12},
        'geometry_pending':'WholeJT8-3 requires rows1..7; unchanged controlled3rows cannot be stage admission. Row-dependent prototype builder/new version needed, original source flags/speed/lifetime/radius/random branches unchanged.',
        'movement_review':'Normal decision cast_groups currently only normal, so active global skills do not explicitly suppress movement via a skill group; no native movement-body proof. Needs declared combined movement policy or actual counter if cast must freeze route.',
        'source_locks':{str(x):sha(x) for x in parent_paths+[JOIN,PLAN,BASE/'source.closure.v1.json',Path(__file__)]}}
def package(kill):
    p=json.loads(JOIN.read_bytes());known={d['id']:d for d in p['definitions']};flame=ROOT/'packages/campaign/chapter08_consumers/flame/module.v4.joint.json';q=json.loads(flame.read_bytes())
    assert sha(flame)=='fa780e59d9e47067b998a5888d44a56214644808c87b3e83493abc2b81c1762d'
    for k,rows in q.items():
        if k not in ('entities','abilities','buffs','rules','selectors','projectiles','behaviors'):continue
        for definition in rows:
            if definition['id'] in known:assert same(definition,known[definition['id']]),definition['id']
            else:known[definition['id']]=definition;p['definitions'].append(definition)
    for name,row,col,hate in [('near',4,7,2),('far',7,12,11)]:
        uid='unit/independent/join/'+name;p['definitions'].append({'id':uid,'kind':'entity','tags':['player',name],'components':{'attributes':{'base':{'max_hp':100000,'atk':50000 if name=='near' else 0,'def':1879,'mres':43,'taunt_level':hate,'one_minus_status_resistance':1}},'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}})
    loop=json.loads((BASE.parent/'flame/loop.profile.v3.json').read_bytes())
    p['scenarioDraft']={'id':'scene/independent/join/'+str(kill),'ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':15},'branches':loop['runtime_branch'],
        'initialEntities':deepcopy(loop['initial_entities'])+[{'definition':OWNER,'instanceAlias':'boss','position':{'row':4,'col':6}},{'definition':'unit/independent/join/near','instanceAlias':'near','position':{'row':4,'col':7}},{'definition':'unit/independent/join/far','instanceAlias':'far','position':{'row':7,'col':12}}]}
    if kill:
        p['definitions'].append({'id':'selector/independent/firstdown','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}]})
        p['definitions'].append({'id':'ability/independent/firstdown','kind':'ability','selector':'selector/independent/firstdown','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
        next(d for d in p['definitions'] if d['id']=='unit/independent/join/near')['components']['abilities']=['ability/independent/firstdown']
        p['scenarioDraft']['commands']=[{'at':1,'action':'skill','source':'near','ability':'ability/independent/firstdown'}]
    p['manifest']['metadata']['independent_fixture']='No author fixture/expected reuse. Actual source25SP device definitions in native finite registration profile; firstdown uses explicitly non-native target-controller ATK50000, original Boss stats unchanged. Original partial3screenrows preserved: controlled transition, never fullstage.'
    return p
def domain(s):return {'world':s.session.world.snapshot(),'tasks':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def run(kill):
    p=package(kill);reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=101804)
    folder=OUT/('firstdown' if kill else 'normal');folder.mkdir(parents=True,exist_ok=True);boundary=100 if kill else 580;end=1800 if kill else 720
    s.session.advance(boundary);initial={'hp':s.ctx.resources.current('boss','hp'),'active':s.ctx.active('boss'),'mode':s.ctx.resources.current('boss','mode')}
    cp=folder/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin),providers=reg);s.session.advance(end-boundary);r.session.advance(end-boundary);head=replay(program,s.export_replay(),providers=reg)
    assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
    summary=[thaw(e) for e in s.session.events if e['type'] in ('ability.started','ability.finished','rebirth.started','rebirth.restored','source.bsnake.screen.volley','buff.applied','buff.removed','hint.marked')]
    (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
    with (folder/'events.jsonl').open('wb') as f:
        for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False)+'\n').encode())
    result={'kill':kill,'boundary':boundary,'initial':initial,'end':end,'final':{'hp':s.ctx.resources.current('boss','hp'),'mode':s.ctx.resources.current('boss','mode')},'CP':True,'head':True,'all_events':True,'observations':summary,'files':{str(x):sha(x) for x in folder.iterdir()}}
    file=folder/'observations.json';file.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(file),'sha256':sha(file)}),flush=True);return result
def main():
    assert implementation_digest()==CORE;OUT.mkdir(parents=True,exist_ok=True);a=audit();(OUT/'source.audit.json').write_bytes((json.dumps(a,ensure_ascii=False,indent=2)+'\n').encode())
    rows=[run(kill) for kill in (False,True)]
    assert sha(JOIN)==a['join_sha256'] and implementation_digest()==CORE
    file=OUT/'observations.json';assert not file.exists();file.write_bytes((json.dumps({'core':CORE,'audit':a,'rows':rows,'source_numeric_assertions_pending':True},ensure_ascii=False,indent=2)+'\n').encode());print(sha(file))
if __name__=='__main__':main()
