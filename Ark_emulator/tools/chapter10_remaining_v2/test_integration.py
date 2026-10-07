"""Actual source lord death/aura/managed descendant on frozen joint runtime."""
import sys,os,json,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter10_remaining_v2.build import build,providers
from tools.chapter10_bloodline_v1.build import entity_id
OUT=ROOT/'validation/campaign/chapter10_remaining_v2';LOG=Path(os.environ['ARKSIM_RUN_DIR']);FACT={}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def fixture():
    p=build();lord=p['entities'][0]['id']
    # Test isolation keeps all owned abilities and dependencies; condition explicit.
    for a in p['abilities']:a['activation']['condition']='False'
    p['entities'].append({'id':'unit/lord/test/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':7000,'atk':100000,'def':0,'mres':0,'block_count':1}},'resources':{'hp':{'role':'health','initial':7000,'capacity':7000}},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'spatial':{},'abilities':['ability/lord/test/kill']}})
    p['selectors'].append({'id':'selector/lord/test/lord','kind':'selector','region':{'type':'all'},'filters':[{'tag':'lord'},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/lord/test/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/lord/test/lord','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    route={'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':7},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':3,'position':{'row':0,'col':0}}]}
    actions=[{'kind':'spawn','spawn':{'definition':definition,'instanceAlias':alias,'position':{'row':0,'col':0},'route':route},'count':1,'managed':True,'blocks_wave':True} for definition,alias in [(lord,'lord'),(entity_id('enemy_1220_dzoms_2'),'keeper')]]
    p['scenarioDraft']={'id':'scene/ch10/remaining_v2/managed_lord','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':9},'resources':{'life':{'initial':99999,'capacity':99999}},'objectives':{'type':'waves','life_resource':'life'},'initialEntities':[{'definition':'unit/lord/test/player','instanceAlias':'player','position':{'row':1,'col':0}}],'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':actions}]},{'fragments':[]}]},'commands':[{'at':7,'action':'skill','source':'player','ability':'ability/lord/test/kill'}]}
    return p
def actual():
    reg=providers();p=fixture();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=1226)
    s.advance(3);atk=s.ctx.attributes.value('lord','atk');base=s.ctx.get('lord',('attributes','base','atk'));keeper=s.ctx.get('keeper',('buffs','instances'))
    FACT['predeath']={'lord_atk':atk,'base_atk':base,'keeper_buffs':thaw(keeper)}
    assert atk==base*1.25 and any(b['definition']=='buff/ch10/remaining/lord_child' for b in keeper)
    s.advance(5);state=s.ctx.state();FACT['postdeath8']=thaw(state)
    assert state['kills']==1 and state['pending_waves']==1 and not state['finished'] and not s.ctx.alive('lord') and s.ctx.resources.current('lord','hp')==0
    assert not any(b['definition']=='buff/ch10/remaining/lord_child' for b in s.ctx.get('keeper',('buffs','instances')))
    entry=next(iter(state['death_spawns'].values()));assert entry['rows'][0]['due']==37 and next(iter(state['timeline']['descendant_pending'].values()))['wave']==0
    s.advance(11);checkpoint=s.checkpoint();path=LOG/'lord19.checkpoint.json';path.write_text(json.dumps(checkpoint),encoding='utf8');r=Engine.restore(program,json.loads(path.read_bytes()),providers=reg)
    s.advance(24);r.advance(24);assert s.checkpoint()==r.checkpoint()
    # The explicit tick3 attributes.value probe records a calculation outside
    # public commands. Preserve its CPP; public command head uses a fresh run.
    public=Engine.create(program,providers=reg,seed=1226);public.advance(43)
    h=replay(program,public.export_replay(),providers=reg)
    assert public.checkpoint()==h.checkpoint()
    FACT['comparisons']={'CPP_with_actual_tick3_attribute_query':True,'full_public_command_head':True,'public_original_event_count':len(public.session.events),'head_event_count':len(h.session.events),'explicit_query_scope':'Tick3 attribute query is retained in original CPP; it is not a public replay command.'}
    child=next(e for e in s.session.world.entities() if e['components']['runtime'].get('spawn_lineage'))
    state=s.ctx.state();FACT['end43']={'kills':state['kills'],'pending':state['pending_waves'],'wave':state['timeline']['wave_index'],'child':thaw(child),'events':[thaw(e) for e in s.session.events if e['type'] in ['entity.died','descendant.issued','descendant.born']],'CPP_head':True}
    assert child['definition_id']==entity_id('enemy_1221_dzomg_2') and state['pending_waves']==0 and state['timeline']['members'][str(child['id'])]['wave']==0 and state['timeline']['wave_index']==0 and not state['finished']
    assert s.ctx.get(child['id'],('spatial','movement','wait_until'))==90 and s.ctx.alive('keeper')
    after=Engine.restore(program,s.checkpoint(),providers=reg);assert after.checkpoint()==s.checkpoint()
    return {'program_fingerprint':program.fingerprint,'checkpoint_sha256':sha(path),'checkpoint_bytes':path.stat().st_size}
def main():
    core=implementation_digest();assert core=='9a7d4a01b7fe0a8d77a39e4b280b330e65670349b6fb2716c1319dabcc491ed9'
    files=[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]+[Path(__file__),ROOT/'tools/chapter10_remaining_v2/build.py',ROOT/'tools/chapter10_remaining_v1/build.py',ROOT/'tools/chapter10_bloodline_v1/build.py']
    before={str(p):sha(p) for p in files};result={'passed':False}
    try:result={'passed':True,**actual()}
    except Exception as e:result={'passed':False,'error':str(e),'traceback':traceback.format_exc()}
    after={str(p):sha(p) for p in files};code=0 if result['passed'] and before==after else 1
    report={'core_before':core,'core_after':implementation_digest(),'actual_exit':code,'result':result,'facts':FACT,'source_before':before,'source_after':after,'source_equal':before==after}
    path=OUT/'integration.actual.v6.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'result':result}));return code
if __name__=='__main__':raise SystemExit(main())
