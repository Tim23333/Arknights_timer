"""Complete native-body source gates on unchanged joint candidate."""
import sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter10_dkmage_source_v1.build import build,providers,BODY,EMPTY
from tools.chapter10_chain_v1.fixture import package
from tools.chapter10_bloodline_v1.build import entity_id
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter10_dkmage_source_v1';OUT.mkdir(parents=True,exist_ok=True);FACT={};REG=providers()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def fixture():
    p=build();target=copy.deepcopy(package()['entities'][1]);target['id']='unit/dkmage/test/target'
    for key,profile in target['components']['elemental']['elements'].items():
        profile['rules']={k:v.replace('/chain/probe','/c10/dkmage_chain') for k,v in profile['rules'].items()}
    target['components']['elemental']['eligibility_rule']=target['components']['elemental']['eligibility_rule'].replace('/chain/probe','/c10/dkmage_chain')
    p['entities'].append(target)
    p['scenarioDraft']={'id':'scene/ch10/dkmage/native','ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':10},'initialEntities':[{'definition':BODY,'instanceAlias':'source','position':{'row':2,'col':1}},*[{'definition':target['id'],'instanceAlias':'target'+str(i),'position':{'row':2,'col':2+i}} for i in range(5)]]}
    return p
def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=1225)
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def continuation(p,at,end,label):
    s=create(p);s.advance(at);path=LOG/(label+'.checkpoint.json');path.write_text(json.dumps(cp(s)),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=REG);s.advance(end-at);r.advance(end-at);h=replay(s.program,s.export_replay(),providers=REG)
    assert cp(s)==cp(r)==cp(h)
    FACT[label+'_proof']={'checkpoint_sha256':sha(path),'bytes':path.stat().st_size,'CPP_full_public_head':True,'program_fingerprint':s.program.fingerprint};return s
def complete_attack():
    s=continuation(fixture(),43,110,'native_attack');events=[thaw(e) for e in s.session.events if e['type'] in ['ability.started','projectile.launched','projectile.hit','elemental.loss']]
    hp=[s.ctx.resources.current('target'+str(i),'hp') for i in range(5)];ep=[s.ctx.get('target'+str(i),('runtime','elemental','remaining','DARK')) for i in range(5)]
    FACT['native_attack']={'events':events,'hp':hp,'EP':ep,'source_hp':s.ctx.resources.current('source','hp'),'owned_abilities':s.ctx.get('source',('abilities',))}
    assert hp==[9450,9532.5,9602.625,9662.23125,10000] and ep==[9835,9859.75,9880.7875,9898.669375,10000]
    starts=[e for e in events if e['type']=='ability.started'];launch=[e for e in events if e['type']=='projectile.launched'];assert launch[0]['time']-starts[0]['time']==37
    assert s.ctx.resources.current('source','hp')==16000 and s.ctx.get('source',('abilities',))==['ability/c10/dkmage_chain']
    s.advance(140);launch=[e for e in s.session.events if e['type']=='projectile.launched'];assert launch[1]['time']-launch[0]['time']==120
    FACT['native_cycle']=[e['time'] for e in launch]
def source_eligibility():
    p=fixture();target=p['entities'][-1];target['components']['selection_state']['category']=4
    s=create(p);s.advance(45);FACT['category4_exclusion']={'launches':len([e for e in s.session.events if e['type']=='projectile.launched'])};assert FACT['category4_exclusion']['launches']==0
    p=fixture();target=p['entities'][-1];target['components']['selection_state']['motion']=2;s=create(p);s.advance(45);assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1
    FACT['source_motion3_accepts_air']=True
def death_source():
    p=fixture();p['entities'][-1]['components']['attributes']['base']['atk']=100000;p['entities'][-1]['components']['abilities']=['ability/dkmage/test/kill']
    p['selectors'].append({'id':'selector/dkmage/test/source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'dkmage'},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/dkmage/test/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/dkmage/test/source','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    route={'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':8},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':3,'position':{'row':0,'col':0}}]}
    scene=p['scenarioDraft'];scene['initialEntities']=[{'definition':p['entities'][-1]['id'],'instanceAlias':'killer','position':{'row':4,'col':8}}];scene.update(resources={'life':{'initial':99999,'capacity':99999}},objectives={'type':'waves','life_resource':'life'},commands=[{'at':7,'action':'skill','source':'killer','ability':'ability/dkmage/test/kill'}],timeline={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':BODY,'instanceAlias':'source','position':{'row':0,'col':0},'route':route},'count':1,'managed':True,'blocks_wave':True}]}]}]})
    s=create(p);s.advance(8);assert s.ctx.state()['kills']==1 and s.ctx.state()['pending_waves']==1 and not s.ctx.state()['finished']
    s=continuation(p,19,43,'native_death');child=next(e for e in s.session.world.entities() if e['components']['runtime'].get('spawn_lineage'));state=s.ctx.state()
    FACT['native_death']={'kills':state['kills'],'pending':state['pending_waves'],'child':thaw(child),'births':[thaw(e) for e in s.session.events if e['type']=='descendant.born']}
    assert child['definition_id']==entity_id('enemy_1221_dzomg_2') and s.ctx.get(child['id'],('spatial','movement','wait_until'))==90 and state['timeline']['members'][str(child['id'])]['wave']==0 and state['pending_waves']==0
def missing_owned_data():
    p=fixture();next(e for e in p['entities'] if e['id']==BODY)['components']['lifecycle']['parameters']['native_owned_data'].clear();s=create(p)
    try:s.advance(50)
    except (ValueError,RuntimeError) as e:FACT['missing_owned_container_error']=str(e);assert EMPTY in str(e)
    else:raise AssertionError('Missing native owned EP source container silently accepted')
def main():
    core=implementation_digest();files=[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]+[Path(__file__),ROOT/'tools/chapter10_dkmage_source_v1/build.py'];before={str(p):sha(p) for p in files};results=[]
    for fn in [complete_attack,source_eligibility,death_source,missing_owned_data]:
        try:fn();results.append({'case':fn.__name__,'passed':True})
        except Exception as e:results.append({'case':fn.__name__,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    after={str(p):sha(p) for p in files};code=0 if all(r['passed'] for r in results) and before==after else 1
    report={'core_before':core,'core_after':implementation_digest(),'actual_exit':code,'source_before':before,'source_after':after,'source_equal':before==after,'results':results,'facts':FACT};path=OUT/'author.actual.v1.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
