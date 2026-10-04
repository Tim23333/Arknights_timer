import sys,json,copy,traceback,subprocess,os,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_pillar_lifecycle_v2_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter09_pillar_lifecycle_v1.build import build,providers,PREFIX,START,READY
OUT=ROOT/'validation/campaign/chapter09_pillar_lifecycle_v2';LOG=Path('E:/ArkSimLogs/runs/chapter09_pillar_lifecycle_author_v2');RESULTS=[];ARTIFACTS=[]
def fixture(direction='right',motion=1,free=False):
    d=build();r,c=3,3;dr,dc={'right':(0,1),'left':(0,-1),'up':(-1,0),'down':(1,0)}[direction]
    for name,hp,atk,side,category,movement,tags in [('attacker',20000,6000,0,1,1,['player']),('enemy',20000,0,1,1,motion,['enemy']),('player',1000,0,0,1,1,['player']),('trap',1000,0,0,2,1,['trap'])]:
        d['entities'].append({'id':'unit/pillar/test/'+name,'kind':'entity','tags':tags,'components':{'attributes':{'base':{'max_hp':hp,'atk':atk,'def':9999,'mres':99}},'resources':{'hp':{'role':'health','initial':hp,'capacity':hp}},'spatial':{},'selection_state':{'side':side,'motion':movement,'category':category,'unit_type':2 if side==1 else 1,'target_free':free if name=='enemy' else False},'lifecycle':{'policy':'policy/ark_lifecycle'},**({'abilities':['ability/pillar/test/hit']} if name=='attacker' else {})}})
    d['selectors']=[{'id':'selector/pillar/test','kind':'selector','region':{'type':'all'},'filters':[{'tag':'pillar'},{'state':'alive'}],'limit':1}]
    d['abilities'].append({'id':'ability/pillar/test/hit','kind':'ability','activation':{'mode':'manual'},'selector':'selector/pillar/test','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    d['scenarioDraft']={'id':'scene/pillar/lifecycle','ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':7},'initialEntities':[{'definition':'unit/'+PREFIX+'body','instanceAlias':'pillar','position':{'row':r,'col':c}},{'definition':'unit/pillar/test/attacker','instanceAlias':'attacker','position':{'row':r-dr,'col':c-dc}},{'definition':'unit/pillar/test/enemy','instanceAlias':'enemy','position':{'row':r+dr,'col':c+dc}},{'definition':'unit/pillar/test/player','instanceAlias':'player','position':{'row':r+2*dr,'col':c+2*dc}},{'definition':'unit/pillar/test/trap','instanceAlias':'trap','position':{'row':r+2*dr,'col':c+2*dc}}]}
    return d
def sim(d=None):return Engine.create(Compiler(providers=providers()).compile(d or fixture()),providers=providers(),seed=1909)
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def hit(s):s.ctx.effects.execute('attacker',['pillar'],{'op':'damage','damage_type':'true','scale':1})
def prepare(s):hit(s);assert s.ctx.resources.current('pillar','hp')==0;s.session.advance(61);assert s.ctx.depletion.state('pillar')['stage']=='ready';hit(s)
def direction_case(direction):
    s=sim(fixture(direction));prepare(s);casts=s.ctx.get('pillar',('runtime','casts'));assert len(casts)==1;cast=next(iter(casts.values()));assert cast['ability']=='ability/'+PREFIX+'collapse_'+direction and 'depletion_owned' in cast
    s.session.advance(45);assert s.ctx.resources.current('enemy','hp')==20000;s.session.advance(1)
    assert s.ctx.resources.current('enemy','hp')==8000 and not s.ctx.alive('pillar') and not s.ctx.alive('player') and not s.ctx.alive('trap')
    ruins=[x for x in s.session.world.entities() if x['definition_id']=='unit/'+PREFIX+'ruin'];assert len(ruins)==2
    assert all(s.ctx.attributes.value(x['id'],'block_count')==3 for x in ruins)
    assert not s.ctx.buffs.controls('enemy')['move']
def source_range_and_damaged_cancel():
    s=sim();s.ctx.set('attacker',('spatial','position'),{'row':1,'col':1});hit(s);assert s.ctx.resources.current('pillar','hp')==5000 and s.ctx.depletion.state('pillar')['generation']==0
    s.ctx.set('attacker',('spatial','position'),{'row':3,'col':2});hit(s);before=s.ctx.depletion.state('pillar');hit(s);assert s.ctx.resources.current('pillar','hp')==0 and s.ctx.depletion.state('pillar')==before
    s.session.advance(60);assert s.ctx.depletion.state('pillar')['stage']=='damaged';s.session.advance(1);assert s.ctx.depletion.state('pillar')['stage']=='ready' and not s.ctx.get('pillar',('runtime','casts'),{})
    hit(s);assert len(s.ctx.get('pillar',('runtime','casts')))==1
def source_pillar_candead_cancel():
    d=fixture();actor=next(e for e in d['entities'] if e['id']=='unit/pillar/test/attacker');other=copy.deepcopy(actor);other['id']='unit/pillar/test/ordinary_source';d['entities'].append(other);d['scenarioDraft']['initialEntities'].append({'definition':other['id'],'instanceAlias':'ordinary_source','position':{'row':3,'col':2}});actor['tags'].append('dupilr')
    s=sim(d);hit(s);assert s.ctx.resources.current('pillar','hp')==5000 and any(b['definition']==READY for b in s.ctx.get('pillar',('buffs','instances')))
    s.ctx.effects.execute('ordinary_source',['pillar'],{'op':'damage','damage_type':'true','scale':1});assert s.ctx.resources.current('pillar','hp')==0 and s.ctx.depletion.state('pillar')['stage']=='collapsing'
def flying_free_and_terrain():
    s=sim(fixture(motion=2));prepare(s);mask=s.ctx.spatial.grid.tile(3,4)['passableMask'];s.session.advance(46);assert s.ctx.resources.current('enemy','hp')==8000
    ruins=[x for x in s.session.world.entities() if x['definition_id']=='unit/'+PREFIX+'ruin'];assert len(ruins)==2
    for ruin in ruins:
        pos=ruin['components']['spatial']['position'];tile=s.ctx.spatial.grid.tile(pos['row'],pos['col']);assert tile['passableMask']==mask and tile['buildableType']==0
    s=sim(fixture(free=True));prepare(s);s.session.advance(46);assert s.ctx.resources.current('enemy','hp')==20000 and not s.ctx.alive('player') and not s.ctx.alive('trap')
def cpp_head_authority_and_tamper():
    d=fixture();d['scenarioDraft']['commands']=[{'at':at,'action':'skill','source':'attacker','ability':'ability/pillar/test/hit'} for at in [0,30,61]]
    s=sim(d);s.session.advance(62);checkpoint=cp(s)
    LOG.mkdir(parents=True,exist_ok=True);path=LOG/'public.checkpoint.json';path.write_text(json.dumps(checkpoint),encoding='utf8');ARTIFACTS.append({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    r=Engine.restore(s.program,checkpoint,providers=providers());s.session.advance(50);r.session.advance(50);assert cp(s)==cp(r)
    h=replay(s.program,s.export_replay(),providers=providers());assert cp(h)==cp(s)
    target=next(x for x in checkpoint['kernel']['world']['entities'] if x['definition_id']=='unit/'+PREFIX+'body');cast=next(iter(target['components']['runtime']['casts'].values()))
    for field,value in [('generation',99),('ability','ability/'+PREFIX+'collapse_left'),('tile_targets',[{'row':0,'col':0}])]:
        changed=copy.deepcopy(checkpoint);entity=next(x for x in changed['kernel']['world']['entities'] if x['id']==target['id']);c=next(iter(entity['components']['runtime']['casts'].values()));c[field]=value
        try:Engine.restore(s.program,changed,providers=providers())
        except ValueError:pass
        else:raise AssertionError('accepted cast tamper '+field)
    changed=copy.deepcopy(checkpoint);c=next(iter(next(x for x in changed['kernel']['world']['entities'] if x['id']==target['id'])['components']['runtime']['casts'].values()));proof=changed['kernel']['events']['records'][c['depletion_schedule_event']-1]
    for task in changed['kernel']['scheduler']['tasks']:
        if task['id'] in c['tasks']:task['at']=63
    for task in proof['payload']['tasks']:task['at']=63
    c['finish_at']=63;proof['payload']['finish_at']=63
    try:Engine.restore(s.program,changed,providers=providers())
    except ValueError:pass
    else:raise AssertionError('coherent early cast task restored')
def forged_and_retire():
    s=sim();prepare(s);before=cp(s);owner=s.session.world.resolve('pillar');cast=next(iter(s.ctx.get(owner,('runtime','casts')).values()))
    s.ctx.abilities.handle_effect(s.session,{'source':owner,'cast':cast['id'],'effect':{'op':'retire','target':'source'},'condition':None});assert cp(s)==before
    s.ctx.abilities._finish(s.session,{'source':owner,'cast':cast['id']});assert cp(s)==before
    try:s.ctx.depletion.damage_gate(s.session.world.resolve('attacker'),owner,{'op':'damage','damage_type':'true','scale':1},6000)
    except ValueError:pass
    else:raise AssertionError('direct pure gate dispatch outside actual attack accepted')
    assert cp(s)==before
    try:s.ctx.abilities.start(owner,cast['ability'])
    except ValueError:pass
    else:raise AssertionError('ordinary start on zero owner accepted')
    try:s.ctx.effects.execute(owner,[owner],{'op':'emit','event':'forged'},cast=copy.deepcopy(cast))
    except ValueError:pass
    else:raise AssertionError('static cloned cast authority accepted')
    assert cp(s)==before;s.ctx.lifecycle.retire(owner,'withdrawn');s.session.advance(50);assert s.ctx.resources.current('enemy','hp')==20000 and not any(x['definition_id']=='unit/'+PREFIX+'ruin' for x in s.session.world.entities())
def synchronous_start_fault_atomic():
    d=fixture();ability=next(a for a in d['abilities'] if a['id']=='ability/'+PREFIX+'collapse_right');ability['activation']['on_start'].append({'op':'random','stream':'source_fault','probability':1,'on_success':[{'op':'modify_resource','resource':'absent','amount':1}]})
    s=sim(d);hit(s);s.session.advance(61);before=cp(s)
    try:hit(s)
    except ValueError:pass
    else:raise AssertionError('late owned start missing resource accepted')
    assert cp(s)==before and not s.ctx.depletion._callbacks and not s.ctx.depletion._entries and not s.ctx.depletion._attacks and not s.ctx.depletion._deliveries
def buff_clear_and_source_direction_current():
    d=fixture();d['buffs'].append({'id':'buff/pillar/test/unretained','kind':'buff'});d['entities'][0]['components']['buffs']['initial'].append('buff/pillar/test/unretained')
    s=sim(d);hit(s);assert not any(b['definition']=='buff/pillar/test/unretained' for b in s.ctx.get('pillar',('buffs','instances')))
    s.session.advance(61);s.ctx.set('attacker',('spatial','position'),{'row':4,'col':3});hit(s);cast=next(iter(s.ctx.get('pillar',('runtime','casts')).values()));assert cast['ability']=='ability/'+PREFIX+'collapse_up'
def no_source_and_ordinary_actor_no_permission():
    s=sim();before=s.ctx.resources.current('pillar','hp');d={'op':'no_source_damage','fixed_amount':6000,'damage_type':'true','attack_type':'NONE','damage_without_modify':True,'ignore_for_sp':False,'node_is_env_damage':True,'env_blackboard_injected':False,'environmental':True,'origin':{'fixture':'source_env'},'rules':{'damage.pipeline':'rule/pillar/test/no_source'}}
    data=fixture();data['rules'].append({'id':'rule/pillar/test/no_source','kind':'rule','contract':'damage.pipeline','implementation':{'type':'expression','expression':"{'accepted': True, 'amount': inputs.effect.fixed_amount, 'allocations': [], 'events': []}"}});s=sim(data);s.ctx.effects.execute(None,['pillar'],d);assert s.ctx.resources.current('pillar','hp')==before and s.ctx.depletion.state('pillar')['generation']==0
    normal=s.session.world.resolve('attacker');beforecp=cp(s)
    try:s.ctx.effects.execute(normal,[normal],{'op':'emit','event':'fake'},cast={'depletion_action':{'owner':normal,'generation':0,'gate':True}})
    except ValueError:pass
    else:raise AssertionError('unowned fake callback on ordinary actor accepted')
    assert cp(s)==beforecp
def cleanup():
    if LOG.exists():
        r=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs_v2.py'),'--run-dir',str(LOG),'--apply','--minimum-age-minutes','0','--completed-pid',str(os.getpid())],capture_output=True,text=True,encoding='utf8');assert r.returncode==0;return json.loads(r.stdout)
def main():
    guard=implementation_digest();source_paths=[Path(__file__),ROOT/'tools/chapter09_pillar_lifecycle_v1/build.py',ROOT/'tools/chapter09_pillar_v1/build_payload.py',ROOT/'tools/chapter09_pillar_v1/source_closure.py',ROOT/'tools/chapter09_pillar_v1/registration.py',ROOT/'tools/chapter09_pillar_v1/bigforce.py',ROOT/'packages/campaign/chapter09_consumers/pillars/source.closure.v1.json',ROOT/'packages/campaign/chapter09_source_prepare/predefines.native.v3.json',ROOT/'packages/campaign/chapter09_source_prepare/duruin.transitive.source.v1.json',ROOT/'ark_emulator/data_range_table.json'];source_before={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths};module_before=hashlib.sha256(json.dumps(build(),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    cases=[('actual_full_source_direction_'+direction,lambda direction=direction:direction_case(direction)) for direction in ['right','left','up','down']]+[('source_in_range_and_two_second_damage_cancellation',source_range_and_damaged_cancel),('native_pillar_tag_candead_and_cancel_branch',source_pillar_candead_cancel),('flying_free_character_trap_ruin_terrain',flying_free_and_terrain),('public_cpp_head_source_owned_and_coherent_task_tamper',cpp_head_authority_and_tamper),('forged_direct_cast_task_and_retire_no_authority',forged_and_retire),('owned_start_late_fault_complete_atomic_rollback',synchronous_start_fault_atomic),('native_retained_buff_clear_and_current_source_direction',buff_clear_and_source_direction_current),('source_environment_immunity_and_ordinary_fake_callback_reject',no_source_and_ordinary_actor_no_permission)]
    clean=[]
    for name,fn in cases:
        try:fn();RESULTS.append({'case':name,'passed':True})
        except Exception as error:RESULTS.append({'case':name,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
        finally:
            result=cleanup()
            if result:clean.append(result)
    source_after={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths};module_after=hashlib.sha256(json.dumps(build(),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    r={'core_before':guard,'core_after':implementation_digest(),'source_before':source_before,'source_after':source_after,'module_before':module_before,'module_after':module_after,'source_guard_equal':guard==implementation_digest() and source_before==source_after and module_before==module_after,'actual_exit':0 if all(x['passed'] for x in RESULTS) and source_before==source_after and module_before==module_after else 1,'results':RESULTS,'cleanup':clean,'artifacts':ARTIFACTS,'raw_deleted':all(not Path(a['path']).exists() for a in ARTIFACTS)}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'author.initial.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r));return r['actual_exit']
if __name__=='__main__':raise SystemExit(main())
