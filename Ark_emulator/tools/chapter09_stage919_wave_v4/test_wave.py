"""Two managed source waves, surviving old actors and actual first-life kill."""
import sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_finale_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter09_stage919_assembly_v1.providers_v3 import providers
from tools.chapter09_stage919_wave_v4.patch import PARENT,OUTPUT,SOURCE,REQUEST
OUT=ROOT/'validation/campaign/chapter09_stage919_wave_v4';LOG=Path(os.environ['ARKSIM_RUN_DIR'])
CORE='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def fixture(path):
    p=json.loads(path.read_bytes());old=copy.deepcopy(p['scenarioDraft']);waves=old['timeline']['waves']
    boss=copy.deepcopy(next(a for f in waves[0]['fragments'] for a in f['actions'] if a.get('spawn',{}).get('definition')=='unit/ch9/mandra/body'))
    other=copy.deepcopy(waves[0]['fragments'][0]['actions'][0]);future=copy.deepcopy(waves[1]['fragments'][0]['actions'][0])
    assert boss['delay_seconds']==other['delay_seconds']==3 and boss['count']==other['count']==1
    for action,name,position in [(boss,'boss',{'row':2,'col':2}),(other,'other',{'row':5,'col':7})]:
        action['spawn'].pop('route');action['spawn']['position']=position;action['spawn']['instanceAlias']=name
        action['spawn'].pop('placement',None)
    future['spawn'].pop('route');future['spawn']['position']={'row':5,'col':6};future['spawn']['instanceAlias']='future';future['spawn'].pop('placement',None)
    p['definitions'] += [
        {'id':'selector/wavepeer/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'},{'state':'alive'}],'limit':1},
        {'id':'ability/wavepeer/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/wavepeer/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':40}}]},
        {'id':'unit/wavepeer/operator','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':41000,'atk':1400,'def':137,'mres':22}},'resources':{'hp':{'initial':41000,'capacity':41000,'role':'health'}},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'spatial':{},'abilities':['ability/wavepeer/kill']}}]
    old.pop('waves',None);old['id']='scene/919/wave/release/'+path.stem;old['map']={'rows':7,'cols':9};old['cards']=[]
    old['initialEntities']=[{'definition':'unit/wavepeer/operator','instanceAlias':'operator','position':{'row':2,'col':3}}]
    old['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[
        {'pre_delay_seconds':waves[0]['pre_delay_seconds'],'post_delay_seconds':waves[0]['post_delay_seconds'],'max_wait_seconds':waves[0]['max_wait_seconds'],'fragments':[{'pre_delay_seconds':0,'actions':[boss,other]}]},
        {**{k:v for k,v in waves[1].items() if k!='fragments'},'fragments':[{**{k:v for k,v in waves[1]['fragments'][0].items() if k!='actions'},'actions':[future]}]}]}
    old['commands']=[{'at':100,'action':'skill','source':'operator','ability':'ability/wavepeer/kill'}];p['scenarioDraft']=old
    return p
def create(path):return Engine.create(Compiler(providers=providers()).compile(fixture(path)),providers=providers(),seed=9194)
def main():
    assert implementation_digest()==CORE;files=[Path(__file__),PARENT,OUTPUT,SOURCE,ROOT/'tools/chapter09_stage919_wave_v4/patch.py',ROOT/'tools/chapter09_stage919_assembly_v1/providers_v3.py']
    files += [p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
    before={str(p):sha(p) for p in files};results=[];facts={};artifacts=[]
    try:
        counter_path=OUT/'v3.missing_release.counter.json';counter=json.loads(counter_path.read_bytes());assert counter['core']==CORE and counter['parent_sha256']==sha(PARENT)
        s=create(OUTPUT);s.advance(101);path=LOG/'waiting.checkpoint.json';path.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=providers());s.advance(150);r.advance(150);assert cp(s)==cp(r)
        completed_held={b['definition'] for b in s.ctx.get('boss',('buffs','instances'))};assert {'buff/ch9/mandra/native_immune','buff/ch9/mandra/shield','buff/ch9/mandra/stone_area','buff/ch9/mandra/invulnerable'}<=completed_held
        assert s.ctx.resources.current('boss','hp')==50000
        s.advance(399);r.advance(399);h=replay(s.program,s.export_replay(),providers=providers());assert cp(s)==cp(r)==cp(h)
        boss=s.session.world.resolve('boss');other=s.session.world.resolve('other');t=s.ctx.state()['timeline'];request=t['finish_requests']['0'];assert request['source']==boss and request['requested_at']==250 and request['parameters']==REQUEST['parameters']
        assert t['wave_index']==1 and s.ctx.alive(boss) and s.ctx.alive(other) and t['members'][str(boss)]['wave']==0 and t['members'][str(other)]['wave']==0
        held={b['definition'] for b in s.ctx.get(boss,('buffs','instances'))};assert {'buff/ch9/mandra/native_immune','buff/ch9/mandra/shield','buff/ch9/mandra/stone_area'}<=held and s.ctx.resources.current(boss,'hp')==50000
        future=[e for e in s.session.events if e['type']=='timeline.action' and e['payload'].get('kind')=='spawn' and e['payload'].get('wave')==1]
        facts['actual_future_actions']=[{'time':e['time'],'payload':thaw(e['payload'])} for e in future]
        assert len(future)==1
        origins=future[0]['payload']['origins'];assert origins['wave_start']==250 and origins['fragment_start']==origins['wave_start']+5*30 and origins['action_start']==origins['fragment_start']+8*30
        assert future[0]['time']==origins['wave_start']+13*30==640
        assert s.ctx.state()['kills']==0 and s.ctx.state()['leaks']==0 and s.ctx.state()['pending_waves']==3
        facts={'requested_at':250,'wave1_entry_tick':250,'native_wave1_fragment_delay_seconds':5,'native_wave1_spawn_delay_seconds':8,'actual_wave1_birth_tick':640,'boss_second_life_hp':50000,'other_wave0_alive':True,'no_tracking_transfer':True,'fixture_input_births':6,'pending_births':3,'kills':0,'leaks':0,'full_CPP_head_equal':True,'held_buffs':sorted(held),'held_buffs_at251':sorted(completed_held),'prior_v3_counter_sha256':sha(counter_path),'actual_future_actions':[{'time':e['time'],'payload':thaw(e['payload'])} for e in future]}
        artifacts.append({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'program_fingerprint':s.program.fingerprint});results.append({'case':'v4_actual_source_completion_releases_native_next_wave_CPP_head','passed':True})
    except Exception as error:results.append({'case':'wave_source_gate','passed':False,'error':str(error),'traceback':traceback.format_exc()})
    after={str(p):sha(p) for p in files};code=0 if all(x['passed'] for x in results) and before==after else 1
    report={'core_before':CORE,'core_after':implementation_digest(),'actual_exit':code,'results':results,'facts':facts,'artifacts':artifacts,'source_before':before,'source_after':after,'source_equal':before==after,'whole_stage':False,'fixture_policy':'Controlled2source waves; same source actor stats and native action delays/counts; routes removed only in fixture to keep old wave actors alive. FullV4stage63input/source routes unchanged.'};path=OUT/'author.wave.final.v4.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
