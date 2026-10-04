"""Real owned Aura/Buff membership, public mode transitions and terminalHP0."""
import json,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_wave_track_v4_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_joint_v4.build_bsnake_partial_join_v1 import providers as partial
from tools.chapter08_flame_device.policies_v1 import providers as flames
from tools.chapter08_bsnake_visual.build_v1 import BASE,CHILD,sha
CORE='4bf1cc96ae41f2850b645c25d772ada1d472f7b0202127fff340a4fc2b0b04c3';OWNER='unit/ch8/bsnake/cadb87696bef4de2';MODULE=BASE/'visual.module.v3.json';BOSS=BASE/'four_modes.wave_source.v5.json';OUT=ROOT/'validation/campaign/chapter08_bsnake_visual_author_v3'
def providers():return {**partial(),**flames()}
def same(a,b):return json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)
def package():
    p=json.loads(BOSS.read_bytes());v=json.loads(MODULE.read_bytes());known={d['id']:d for d in p['definitions']}
    for k in ('buffs','selectors','rules'):
        for d in v[k]:assert d['id'] not in known;p['definitions'].append(d);known[d['id']]=d
    body=known[OWNER]['components'];owned_before=list(body['abilities']);body['buffs']['initial']+=v['manifest']['metadata']['initial_owned_buffs']
    body['rebirth']['retain_buffs']=list(dict.fromkeys(body['rebirth']['retain_buffs']+v['manifest']['metadata']['rebirth_retained_buffs']))
    terminal=body['rebirth']['zero_restore_lifecycle'];terminal['retained_buffs']=list(dict.fromkeys(terminal['retained_buffs']+v['manifest']['metadata']['terminal_retained_buffs']))
    assert body['abilities']==owned_before and body['attributes']['base']['max_hp']==50000
    flame=json.loads((BASE.parent/'flame/module.v4.joint.json').read_bytes())
    for k in ('entities','buffs','selectors','rules','projectiles','abilities'):
        for d in flame.get(k,[]):
            if d['id'] in known:assert same(d,known[d['id']])
            else:known[d['id']]=d;p['definitions'].append(d)
    states=[('ground',0,1,1,{}),('air',0,2,1,{}),('free',0,1,1,{'target_free':True}),('camo',0,1,1,{'camouflage':True}),('enemy',1,1,1,{}),('neutral',2,1,1,{}),('category2',0,1,2,{})]
    for name,side,motion,category,flags in states:
        uid='unit/visual/fixture/'+name;p['definitions'].append({'id':uid,'kind':'entity','tags':[name],'components':{'attributes':{'base':{'max_hp':2345,'atk':0,'def':321,'mres':54}},'resources':{'hp':{'initial':2345,'capacity':2345,'role':'health'}},'selection_state':{'side':side,'motion':motion,'category':category,'unit_type':1,**flags},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['definitions'].append({'id':'unit/visual/controller','kind':'entity','tags':['controller'],'components':{'attributes':{'base':{'max_hp':1456,'atk':0,'def':10,'mres':0}},'resources':{'hp':{'initial':1456,'capacity':1456,'role':'health'}},'spatial':{},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':1},'abilities':['ability/visual/mode2','ability/visual/mode3','ability/visual/mode1','ability/visual/retire','ability/visual/firstdown'],'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['definitions'].append({'id':'selector/visual/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}]})
    for name,effect in [('mode2',{'op':'modify_resource','resource':'mode','value':2}),('mode3',{'op':'modify_resource','resource':'mode','value':3}),('mode1',{'op':'modify_resource','resource':'mode','value':1}),('retire',{'op':'retire','parameters':{'reason':'withdrawn'}}),('firstdown',{'op':'instant_kill','parameters':{'cause':'visual_fixture_firstdown','skip_rebirth':False}})]:
        p['definitions'].append({'id':'ability/visual/'+name,'kind':'ability','selector':'selector/visual/boss','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':effect}]})
    loop=json.loads((BASE.parent/'flame/loop.profile.v3.json').read_bytes());p['scenarioDraft']={'id':'scene/visual/author','ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':15},'branches':loop['runtime_branch'],'initialEntities':deepcopy(loop['initial_entities'])+[{'definition':'unit/visual/controller','instanceAlias':'controller','position':{'row':0,'col':0}}]+[{'definition':'unit/visual/fixture/'+name,'instanceAlias':name,'position':{'row':0,'col':i+1}} for i,(name,*_) in enumerate(states)],
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':OWNER,'instanceAlias':'boss','position':{'row':4,'col':13}},'count':1,'managed':True,'blocks_wave':True}]}]},{'fragments':[{'actions':[]}]}]}}
    p['manifest']['metadata']['visual_fixture']='Original V5 Boss stats/owned10/lifecycle retained; only finite visualBuff bindings added. Public controller modeprojection/instantkill is explicit testability fixture, not native stage/rebirth fullscreen proof.'
    return p
def markers(s):return sorted(name for name in ('ground','air','free','camo','enemy','neutral','category2','boss') if any(b['definition']==CHILD for b in s.ctx.entity(name)['components'].get('buffs',{}).get('instances',[])))
def domain(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def run(kind):
    p=package();commands=[(2,'mode2'),(5,'mode3'),(8,'mode1'),(11,'mode2'),(14,'retire')] if kind=='mode_lifecycle' else [(1,'firstdown'),(160,'firstdown')]
    p['scenarioDraft']['commands']=[{'at':t,'action':'skill','source':'controller','ability':'ability/visual/'+a} for t,a in commands]
    s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=844);folder=OUT/kind;folder.mkdir(parents=True,exist_ok=True);observations=[]
    checkpoints=[1,3,6,9,12,15] if kind=='mode_lifecycle' else [1,2,152,161,311,312]
    boundary=6 if kind=='mode_lifecycle' else 162;end=17 if kind=='mode_lifecycle' else 314
    clone=None;cp=None;pin=None
    for t in sorted(set(checkpoints+[boundary,end])):
        s.session.advance(t-s.session.time);observations.append({'time':t,'members':markers(s),'HP':s.ctx.resources.current('boss','hp'),'active':s.ctx.active('boss'),'mode':s.ctx.resources.current('boss','mode')})
        if t==boundary:cp=folder/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());clone=Engine.restore(s.program,load_bound(cp,pin),providers=providers())
    clone.session.advance(end-boundary);head=replay(s.program,s.export_replay(),providers=providers());assert domain(s)==domain(clone)==domain(head) and tuple(s.session.events)==tuple(clone.session.events)==tuple(head.session.events)
    expected=['air','free','ground']
    if kind=='mode_lifecycle':assert [o['members'] for o in observations if o['time'] in checkpoints]==[[],expected,expected,[],expected,[]],observations
    else:
        assert next(o for o in observations if o['time']==152)['members']==expected
        last=next(o for o in observations if o['time']==312);assert last['members']==expected and last['HP']==0 and last['active'] and last['mode']==3,last
    assert all(s.ctx.resources.current(name,'hp')==2345 for name in ('ground','air','free','camo','enemy','neutral','category2'))
    (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
    with (folder/'events.jsonl').open('wb') as f:
        for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False)+'\n').encode())
    return {'case':kind,'observations':observations,'CP':True,'head':True,'all_events':True,'targetHP_unchanged':True,'files':{str(q):sha(q) for q in folder.iterdir()}}
def main():
    assert implementation_digest()==CORE;OUT.mkdir(exist_ok=True);rows=[run(k) for k in ('mode_lifecycle','terminal_HP0')];assert implementation_digest()==CORE
    out=OUT/'report.json';assert not out.exists();out.write_bytes((json.dumps({'status':'two_source_visual_cases_passed','core':CORE,'visual_module_sha256':sha(MODULE),'boss_source_sha256':sha(BOSS),'rows':rows,'renderer_rendered':False,'whole_stage':False},ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()
