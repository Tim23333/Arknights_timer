"""Actual source bloodline behavior and owned descendant boundary evidence."""
import sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_bloodline_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter10_bloodline_v1.build import build_all,providers,entity_id,KEYS,MARK,BLOCK,DEATH
OUT=ROOT/'validation/campaign/chapter10_bloodline_v1';LOG=Path(os.environ['ARKSIM_RUN_DIR']);FACTS={};ARTIFACTS=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def player():return {'id':'unit/blood/test/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':7000,'atk':10000,'def':0,'mres':0,'block_count':1,'attack_speed_ratio':1}},'resources':{'hp':{'role':'health','capacity':7000,'initial':7000}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'deployable':{'base_cost':0,'terrain':'ground','capacity':1,'cooldown_seconds':0},'abilities':['ability/blood/test/kill']}}
def fixture(key='enemy_1222_dpvt',timeline=False,wait=True):
    p=build_all();p['entities'].append(player());p['selectors'].append({'id':'selector/blood/test/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1});p['abilities'].append({'id':'ability/blood/test/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/blood/test/enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    route={'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':7},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':3,'position':{'row':0,'col':0}}] if wait else []}
    source={'definition':entity_id(key),'instanceAlias':'parent','position':{'row':0,'col':0},'route':route}
    scene={'id':'scene/bloodline/'+key,'ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':9},'resources':{'life':{'initial':99999,'capacity':99999}},'objectives':{'type':'waves','life_resource':'life'},'initialEntities':[{'definition':'unit/blood/test/player','instanceAlias':'player','position':{'row':1,'col':0}}],'commands':[]}
    if timeline:scene['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','spawn':source,'count':1,'managed':True,'blocks_wave':True}]}]},{'fragments':[]}]}
    else:scene['initialEntities'].append(source)
    p['scenarioDraft']=scene;return p
def create(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=1220)
def death_and_wait_CPP():
    for key in ['enemy_1222_dpvt','enemy_1222_dpvt_2']:
        p=fixture(key,True);p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'player','ability':'ability/blood/test/kill'}];s=create(p);s.advance(8)
        assert s.ctx.state()['kills']==1 and not s.ctx.alive('parent') and not s.ctx.state()['finished'] and s.ctx.state()['pending_waves']==1
        ledger=s.ctx.state()['death_spawns'];entry=next(iter(ledger.values()));assert entry['rows'][0]['due']==37
        path=LOG/(key+'.checkpoint.json');path.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=providers());s.advance(32);r.advance(32);assert cp(s)==cp(r)
        child=next(e for e in s.session.world.entities() if e['components']['runtime'].get('spawn_lineage'));assert child['definition_id']==entity_id('enemy_1220_dzoms_2' if key.endswith('_2') else 'enemy_1220_dzoms')
        assert s.ctx.get(child['id'],('spatial','movement','wait_until'))==90 and s.ctx.state()['timeline']['members'][str(child['id'])]['wave']==0 and s.ctx.state()['pending_waves']==0
        assert s.ctx.state()['timeline']['wave_index']==0 and not s.ctx.state()['finished'];h=replay(s.program,s.export_replay(),providers=providers());assert cp(h)==cp(s)
        after=Engine.restore(s.program,cp(s),providers=providers());assert cp(after)==cp(s)
        FACTS[key]={'death_tick':7,'birth_tick':37,'immediate_kills':1,'wait_deadline':90,'managed_wave':0,'child':child['id'],'definition':child['definition_id'],'CPP_full_head':True};ARTIFACTS.append({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size})
def bloodsucker_marker_DR_types():
    for key in ['enemy_1220_dzoms','enemy_1220_dzoms_2','enemy_1221_dzomg','enemy_1221_dzomg_2']:
        s=create(fixture(key));assert any(b['definition']==MARK for b in s.ctx.get('parent',('buffs','instances')))
        before=s.ctx.resources.current('parent','hp');defense=s.ctx.attributes.value('parent','def');res=s.ctx.attributes.value('parent','mres')
        for kind,expected in [('physical',max(1000-defense,50)*.1),('arts',1000*(1-res/100)*.1),('true',1000)]:
            old=s.ctx.resources.current('parent','hp');s.ctx.effects.execute('player',['parent'],{'op':'damage','damage_type':kind,'scale':.1});assert abs(old-s.ctx.resources.current('parent','hp')-expected)<1e-8
def blocked_stacks_cap_release():
    p=fixture('enemy_1220_dzoms');p['scenarioDraft'].pop('objectives');p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1];p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':1}
    for i in range(8):p['scenarioDraft']['initialEntities'].append({'definition':entity_id('enemy_1220_dzoms'),'instanceAlias':'s'+str(i),'position':{'row':0,'col':1},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':7},'checkpoints':[]}})
    s=create(p);s.advance(2);child=next(b for b in s.ctx.get('player',('buffs','instances')) if b['definition']==BLOCK)
    assert len(child['aura_leases'])==7 and child['stacks']==6 and s.ctx.attributes.value('player','block_count')==7
    s.ctx.lifecycle.retire('s0','withdrawn');s.ctx.lifecycle.retire('s1','withdrawn');s.advance(1);assert s.ctx.attributes.value('player','block_count')==7 # previously unblocked8th now legitimately joins
    for i in range(2,8):s.ctx.lifecycle.retire('s'+str(i),'withdrawn')
    s.advance(1);assert s.ctx.attributes.value('player','block_count')==1 and not any(b['definition']==BLOCK for b in s.ctx.get('player',('buffs','instances')))
def melee_source_frames():
    for key,frame in [('enemy_1220_dzoms',12),('enemy_1220_dzoms_2',12),('enemy_1222_dpvt',35),('enemy_1222_dpvt_2',35)]:
        p=fixture(key,False,False);p['scenarioDraft'].pop('objectives');p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':0};s=create(p);s.advance(frame+2)
        hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==s.session.world.resolve('parent')];assert hits and hits[0]['time']==frame+1

def nonzero_route_cursor():
    p=fixture('enemy_1222_dpvt',True,False);p['scenarioDraft']['commands']=[{'at':100,'action':'skill','source':'player','ability':'ability/blood/test/kill'}];s=create(p);s.advance(101)
    issue=next(e for e in s.session.events if e['type']=='descendant.issued');spatial=issue['payload']['snapshot']['components']['spatial'];assert spatial['movement']['path_index']>=2 and spatial['position']['col']>2
    restored=Engine.restore(s.program,cp(s),providers=providers());s.advance(35);restored.advance(35);assert cp(s)==cp(restored)
    child=next(e for e in s.session.world.entities() if e['components']['runtime'].get('spawn_lineage'));assert child['components']['spatial']['position']['col']>spatial['position']['col']-.11
    head=replay(s.program,s.export_replay(),providers=providers());assert cp(head)==cp(s);FACTS['nonzero_route']={'parent_cursor':spatial['movement']['path_index'],'parent_col':spatial['position']['col'],'child_col':child['components']['spatial']['position']['col'],'CPP_head':True}

def restore_and_callback_tamper():
    p=fixture('enemy_1222_dpvt',True);p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'player','ability':'ability/blood/test/kill'}];s=create(p);s.advance(8);before=cp(s);entry=next(iter(s.ctx.state()['death_spawns'].values()));key=next(iter(s.ctx.state()['death_spawns']));row=entry['rows'][0]
    try:s.ctx.death_spawns._dispatch(s.session,{'ledger':key,'slot':row['slot']})
    except ValueError as error:assert 'actual owned scheduled task' in str(error)
    else:raise AssertionError('Copied dead callback obtained capability')
    assert cp(s)==before
    for name in ['due','stamp','missingledger','orphan','context']:
        bad=copy.deepcopy(before);battle=next(e for e in bad['kernel']['world']['entities'] if e['definition_id']=='system/battle');state=battle['components']['state'];ledger=state['death_spawns'];changed=next(iter(ledger.values()));changedrow=changed['rows'][0]
        if name=='due':changedrow['due']=8;next(t for t in bad['kernel']['scheduler']['tasks'] if t['id']==changedrow['task'])['at']=8
        elif name=='stamp':changed['stamp']['death']=0
        elif name=='missingledger':state['death_spawns']={}
        elif name=='orphan':state['death_spawns']={};state['pending_waves']=0
        else:changedrow['decision']['context']['owner']['id']=2
        try:Engine.restore(s.program,bad,providers=providers())
        except ValueError:pass
        else:raise AssertionError('Restored tamper accepted '+name)
    s.advance(32);born=cp(s);bad=copy.deepcopy(born);battle=next(e for e in bad['kernel']['world']['entities'] if e['definition_id']=='system/battle');battle['components']['state']['death_spawns']={}
    try:Engine.restore(s.program,bad,providers=providers())
    except ValueError as error:assert 'Missing restored death spawn issuance ledger' in str(error)
    else:raise AssertionError('Born child survived missing issuance ledger')
    bad=copy.deepcopy(born);child=next(e for e in bad['kernel']['world']['entities'] if e['components'].get('runtime',{}).get('spawn_lineage'));child['components']['runtime']['spawn_lineage']['slot']='foreign'
    try:Engine.restore(s.program,bad,providers=providers())
    except ValueError:pass
    else:raise AssertionError('Forged child lineage accepted')
    FACTS['tamper']={'direct_copied_callback_rejected':True,'pending_due_stamp_context_orphan_rejected':True,'born_missing_ledger_rejected_without_cache_edits':True,'child_reverse_link_rejected':True}

def spawn_late_fault_rollback():
    p=fixture('enemy_1222_dpvt',True);p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'player','ability':'ability/blood/test/kill'}]
    def fail(inputs,params,context):raise ValueError('source placement late fault after real RNG')
    reg=providers();reg['fault/placement']={'callable':fail,'version':'1'};next(r for r in p['rules'] if r['id']=='rule/ch10/bloodline/placement')['implementation']['provider']='fault/placement';s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=1220);s.advance(37);before=cp(s);calls=[];sample=s.session.random.sample
    def observed(stream):calls.append(stream);return sample(stream)
    s.session.random.sample=observed
    captured=[]
    def stores():return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'events':s.session._events.snapshot(),'random':s.session.random.snapshot(),'attribute_cache':s.ctx.attributes.checkpoint_cache()}
    def capture_task():
        task=s.session.scheduler.peek()
        if s.session._atomic_depth==0 and task is not None and task['kind']=='domain.death_spawn':captured.append(stores())
        return None
    s.session.register_atomic_participant('test.failing_task_observation',capture_task,lambda value:None)
    try:s.advance(1)
    except (ValueError,RuntimeError) as error:assert 'source placement late fault after real RNG' in str(error)
    else:raise AssertionError('Late fault not raised')
    assert calls==['ch10/bloodline/descendants']*2
    after=stores();assert captured and after==captured[0];FACTS['latefault']={'actual_RNG_draw_calls':2,'failing_owned_task_World_jobs_RNG_events_cache_exact_rollback':True,'before_task_clock':s.session.time,'failure_record':s.session._failure,'scope':'Atomic boundary before actual domain.death_spawn; earlier committed same-tick system work retained, failure marker recorded honestly'}

def main():
    before=implementation_digest();files=[Path(__file__),ROOT/'tools/chapter10_bloodline_v1/build.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')];guards={str(p):sha(p) for p in files};results=[]
    for fn in [death_and_wait_CPP,bloodsucker_marker_DR_types,blocked_stacks_cap_release,melee_source_frames,nonzero_route_cursor,restore_and_callback_tamper,spawn_late_fault_rollback]:
        try:fn();results.append({'case':fn.__name__,'passed':True})
        except Exception as error:results.append({'case':fn.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    after={str(p):sha(p) for p in files};code=0 if all(r['passed'] for r in results) and guards==after else 1;report={'core_before':before,'core_after':implementation_digest(),'actual_exit':code,'results':results,'facts':FACTS,'artifacts':ARTIFACTS,'source_before':guards,'source_after':after,'source_equal':guards==after};path=OUT/'author.strict.v7.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
