"""Native ordinary attacks/vampire/base-lord death integration."""
import sys,os,json,hashlib,traceback,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter10_stage17_ordinary_v1.build import build,providers,entity_id,LORD,VAMPIRE
from tools.chapter10_bloodline_v1.build import entity_id as blood_id
from tools.campaign_elemental_receivers_v1.build import providers as receiver_providers
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter10_stage17_ordinary_v1';OUT.mkdir(parents=True,exist_ok=True);FACT={};REG={**providers(),**receiver_providers()};sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def fixture(key):
    p=build(key);player={'id':'unit/stage17/test/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':7000,'atk':1000,'def':0,'mres':40,'block_count':1}},'resources':{'hp':{'role':'health','initial':7000,'capacity':7000}},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'spatial':{'blocking':True},'abilities':['ability/stage17/test/hurt']}}
    player['components']['deployable']={'base_cost':0,'terrain':'ground','capacity':1,'cooldown_seconds':0}
    p['entities'].append(player)
    p['selectors'].append({'id':'selector/stage17/test/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':key},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/stage17/test/hurt','kind':'ability','activation':{'mode':'manual'},'selector':'selector/stage17/test/enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    from tools.campaign_elemental_receivers_v1.build import mount
    mount(p,entities=['unit/stage17/test/player'])
    p['scenarioDraft']={'id':'scene/stage17/'+key,'ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':9},'initialEntities':[{'definition':'unit/stage17/test/player','instanceAlias':'player','position':{'row':0,'col':1}},{'definition':entity_id(key),'instanceAlias':'source','position':{'row':0,'col':1},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':8},'checkpoints':[]}}],'commands':[]}
    return p
def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=1229)
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def proof(p,at,end,label):
    s=create(p);s.advance(at);path=LOG/(label+'.checkpoint.json');path.write_text(json.dumps(cp(s)),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=REG);s.advance(end-at);r.advance(end-at);h=replay(s.program,s.export_replay(),providers=REG);assert cp(s)==cp(r)==cp(h)
    FACT[label+'_CPP_head']={'passed':True,'sha256':sha(path),'bytes':path.stat().st_size};return s
def darmy():
    p=fixture('enemy_1229_darmy');s=proof(p,12,19,'darmy');damage=[thaw(e) for e in s.session.events if e['type']=='damage.accepted'];FACT['darmy']={'damage':damage,'HP':s.ctx.resources.current('player','hp'),'DARK':s.ctx.get('player',('runtime','elemental','remaining','DARK')),'blocked_by':s.ctx.get('source',('runtime','blocked_by'))}
    assert len(damage)==1 and damage[0]['time']==18 and damage[0]['payload']['amount']==144 and FACT['darmy']['DARK']==911.2 and s.ctx.resources.current('source','hp')==4200
    p=fixture('enemy_1229_darmy');p['scenarioDraft']['initialEntities'][1]['position']={'row':1,'col':0};p['scenarioDraft']['initialEntities'][1]['route']['startPosition']={'row':1,'col':0};s=create(p);s.advance(19);assert not [e for e in s.session.events if e['type']=='damage.accepted'];FACT['darmy_unblocked_no_attack']=True
def slime():
    p=fixture('enemy_1228_dslime');p['scenarioDraft']['commands']=[{'at':0,'action':'skill','source':'player','ability':'ability/stage17/test/hurt'}];s=proof(p,3,8,'slime');events=[thaw(e) for e in s.session.events if e['type'] in ['damage.accepted','healing.accepted']];FACT['slime']={'events':events,'source_HP':s.ctx.resources.current('source','hp')}
    assert s.ctx.resources.current('source','hp')==3118.8 and s.ctx.resources.current('player','hp')==6946 and len([e for e in events if e['type']=='healing.accepted'])==1
    s.ctx.buffs.remove('source',VAMPIRE);old=s.ctx.resources.current('source','hp');s.advance(18);assert s.ctx.resources.current('source','hp')==old;FACT['slime_removed_native_buff_disables_heal']=True
def lord():
    p=fixture('enemy_1226_dklord');p['scenarioDraft']['initialEntities'][0]['position']={'row':1,'col':8};p['scenarioDraft']['initialEntities'][1]['position']={'row':0,'col':0};p['scenarioDraft']['initialEntities'][1]['route']={'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':8},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':3,'position':{'row':0,'col':0}}]}
    for i in range(7):p['scenarioDraft']['initialEntities'].append({'definition':blood_id('enemy_1220_dzoms'),'instanceAlias':'member'+str(i),'position':{'row':1,'col':i}})
    q=create(p);q.advance(2);value=q.ctx.attributes.value('source','atk');FACT['lord7']={'ATK':value,'HP':q.ctx.resources.current('source','hp')};assert value==1900 and q.ctx.resources.current('source','hp')==14000
    for i in range(3):q.ctx.lifecycle.retire('member'+str(i),'withdrawn')
    q.advance(1);assert q.ctx.attributes.value('source','atk')==1600
    p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:2];source=p['scenarioDraft']['initialEntities'].pop();p['scenarioDraft'].update(resources={'life':{'initial':99999,'capacity':99999}},objectives={'type':'waves','life_resource':'life'},timeline={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','spawn':source,'count':1,'managed':True,'blocks_wave':True}]}]}]})
    next(e for e in p['entities'] if e['id']=='unit/stage17/test/player')['components']['attributes']['base']['atk']=100000
    p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'player','ability':'ability/stage17/test/hurt'}];s=create(p);s.advance(8);assert s.ctx.state()['kills']==1 and s.ctx.state()['pending_waves']==1 and not s.ctx.state()['finished'];s=proof(p,19,43,'lord_death');child=next(e for e in s.session.world.entities() if e['components']['runtime'].get('spawn_lineage'));assert child['definition_id']==blood_id('enemy_1221_dzomg') and s.ctx.get(child['id'],('spatial','movement','wait_until'))==90
    FACT['lord_death']={'child':child['definition_id'],'births':[thaw(e) for e in s.session.events if e['type']=='descendant.born'],'kills':s.ctx.state()['kills']}
def main():
    core=implementation_digest();files=[f for f in (CAND/'ark_sim').rglob('*') if f.is_file() and f.suffix in ['.py','.json']]+[Path(__file__),ROOT/'tools/chapter10_stage17_ordinary_v1/build.py'];before={str(p):sha(p) for p in files};results=[]
    for f in [darmy,slime,lord]:
        try:f();results.append({'case':f.__name__,'passed':True})
        except Exception as e:results.append({'case':f.__name__,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    after={str(p):sha(p) for p in files};code=0 if all(r['passed'] for r in results) and before==after else 1
    report={'core_before':core,'core_after':implementation_digest(),'actual_exit':code,'source_before':before,'source_after':after,'source_equal':before==after,'results':results,'facts':FACT};path=OUT/'author.actual.v3.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
