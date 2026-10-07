"""Independent base lord death birth on final core94; own wave/route/RNG oracle."""
import copy,hashlib,json,os,random,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];LOCK=ROOT/'validation/campaign/campaign_elemental_lease_v4/freeze.functional.v4.json'
f=json.loads(LOCK.read_bytes());candidate=Path(f['candidate']);sys.path.insert(0,str(candidate));sys.path.insert(1,str(ROOT))
from tools.chapter10_stage17_ordinary_peer_v1 import verify as v
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.chapter10_stage17_ordinary_v1.build import build,providers,entity_id,LORD,VAMPIRE
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import write_checkpoint,load_checkpoint,observations
v.Compiler=Compiler;v.Engine=Engine;v.thaw=thaw;v.digest=digest;v.replay=replay;v.build=build;v.providers=providers;v.entity_id=entity_id;v.LORD=LORD;v.VAMPIRE=VAMPIRE
v.write_checkpoint=write_checkpoint;v.load_checkpoint=load_checkpoint;v.observations=observations;v.LOG=Path(os.environ['ARKSIM_RUN_DIR'])
def main():
    assert implementation_digest()==f['core'];guards={str(candidate/k):h for k,h in f['source_inventory'].items()};assert all(v.sha(p)==h for p,h in guards.items())
    result={'core':implementation_digest(),'passed':False,'facts':{}}
    try:
        p,source=v.scene('enemy_1226_dklord');player=next(e for e in p['entities'] if e['id']=='unit/peer/ordinary/player')
        hp=source['components']['attributes']['base']['max_hp'];player['components']['attributes']['base']['atk']=hp+113
        v.control(p,'kill_lord',{'op':'damage','target':3,'damage_type':'true','scale':1},11)
        keeper=copy.deepcopy(player);keeper['id']='unit/peer/ordinary/keeper';keeper['tags']=['enemy','keeper'];keeper['components']['abilities']=[];keeper['components'].pop('deployable');keeper['components']['selection_state']['side']=1;p['entities'].append(keeper)
        route={'motionMode':'WALK','startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':9},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':6,'position':{'row':1,'col':1}}]}
        keep_route={'motionMode':'WALK','startPosition':{'row':6,'col':1},'endPosition':{'row':6,'col':9},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':7,'position':{'row':6,'col':1}}]}
        draft=p['scenarioDraft'];draft.update(initialEntities=[{'definition':player['id'],'instanceAlias':'player','position':{'row':7,'col':10}}],
          resources={'life':{'initial':777,'capacity':777}},objectives={'type':'waves','life_resource':'life'},
          timeline={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[
            {'kind':'spawn','spawn':{'definition':source['id'],'instanceAlias':'source','position':{'row':1,'col':1},'route':route},'count':1,'managed':True,'blocks_wave':True},
            {'kind':'spawn','spawn':{'definition':keeper['id'],'instanceAlias':'keeper','position':{'row':6,'col':1},'route':keep_route},'count':1,'managed':True,'blocks_wave':True}]}]}]})
        s=v.create(p,'base_lord_death');s.advance(12);assert s.ctx.state()['kills']==1 and s.ctx.state()['pending_waves']==1
        s=v.cpp(s,25,70,'base_lord_death')
        native=p['manifest']['metadata']['native_variant']['native_enemy']['resolved'];bb={r['key']:r['valueStr'] if r['valueStr'] is not None else r['value'] for r in native['talentBlackboard']}
        births=v.events(s,'descendant.born');assert len(births)==1 and births[0]['time']==11+round(bb['deathrattle.delay']*30)
        child=s.ctx.entity(births[0]['payload']['child']);assert child['definition_id']=='unit/ch10/bloodline/'+bb['deathrattle.enemy_key']
        assert child['components']['spatial']['movement']['wait_until']==180 and child['components']['spatial']['route']['endPosition']=={'row':1,'col':9}
        members=s.ctx.state()['timeline']['members'];assert members[str(child['id'])]['wave']==members[str(s.session.world.resolve('keeper'))]['wave']==0 and s.ctx.active('keeper')
        stream='ch10/bloodline/descendants';samples=[x for x in thaw(s.session.random.snapshot())['samples'] if x['stream']==stream]
        seed=int.from_bytes(hashlib.sha256(json.dumps([12261729,stream],ensure_ascii=False,separators=(',',':')).encode()).digest(),'big');rng=random.Random(seed);expected=[rng.random(),rng.random()]
        assert [x['value'] for x in samples]==expected;bound=.10000000149011612;position=births[0]['payload']['position']
        assert all(position[k]==1+(2*x-1)*bound for k,x in zip(('row','col'),expected))
        assert s.ctx.state()['pending_waves']==0 and not s.ctx.state()['finished']
        result.update(passed=True,facts={'source_HP':hp,'raw_BB_child':bb['deathrattle.enemy_key'],'raw_BB_delay':bb['deathrattle.delay'],
          'dead_tick':11,'born_tick':births[0]['time'],'wait_until':180,'same_wave_keeper_active':True,'child_position':position,'named_RNG':samples})
    except Exception as error:result.update(error=str(error),traceback=traceback.format_exc())
    result.update(actual_CP_head_proofs=v.PROOFS,source_unchanged=all(v.sha(p)==h for p,h in guards.items()),source_guards=guards,peer_sha256=v.sha(__file__),whole_stage_approval=False,client_verified=False)
    v.OUT.mkdir(parents=True,exist_ok=True);(v.OUT/'death.94.v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':result['passed'],'error':result.get('error')}),flush=True)
    return 0 if result['passed'] and result['source_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
