"""Independent source assembly vectors and actual obstacle combat fixtures."""
import sys, os, json, copy, hashlib, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=(ROOT/'../unpack_work/campaign_c9_finale_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter09_stage919_assembly_v1.providers_v2 import providers
PACKAGE=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v2.life99999.json'
SOURCE=ROOT/'packages/campaign/chapter09_source_prepare/source.plan.v1.json'
OUT=ROOT/'validation/campaign/chapter09_stage919_peer'
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT.mkdir(parents=True,exist_ok=True)
DATA=json.loads(PACKAGE.read_bytes());NATIVE=json.loads(SOURCE.read_bytes())['stages']['level_main_09-17']['native_document']
CORE='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18'
FACTS={};ARTIFACTS=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def definition(name):return next(d['id'] for d in DATA['definitions'] if d['kind']=='entity' and d['id'].startswith('unit/ch9/'+name+'/'))
def fixture(name='dugago',blocked=True):
    p=copy.deepcopy(DATA);scene=copy.deepcopy(DATA['scenarioDraft'])
    for key in ['timeline','waves','branches','scheduledEffects','routes','cards']:scene.pop(key,None)
    scene['id']='scene/919/independent/'+name+('/blocked' if blocked else '/range');scene['map']={'rows':7,'cols':9}
    scene['initialEntities']=[{'definition':definition(name),'instanceAlias':'enemy','position':{'row':3,'col':2},'route':{'motionMode':'WALK','startPosition':{'row':3,'col':2},'endPosition':{'row':3,'col':7},'checkpoints':[]}},
        {'definition':'unit/ch9/pillar/ruin','instanceAlias':'ruin','position':{'row':3,'col':2 if blocked else 4}},
        {'definition':'unit/ch9/pillar/ruin','instanceAlias':'foreign','position':{'row':4,'col':3}}]
    if not blocked:scene['initialEntities'][0].pop('route')
    scene['commands']=[];p['scenarioDraft']=scene
    return p
def sim(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=9197)
def proof(s,label,ticks=35):
    s.advance(2);path=LOG/(label+'.checkpoint.json');path.write_text(json.dumps(s.checkpoint()),encoding='utf8')
    r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=providers());s.advance(ticks);r.advance(ticks)
    h=replay(s.program,s.export_replay(),providers=providers());assert cp(s)==cp(r)==cp(h)
    ARTIFACTS.append({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'CPP_full_public_head':True})
    return s
def gargoyle_actual_ruin():
    s=sim(fixture());s.advance(1);enemy=s.session.world.resolve('enemy');ruin=s.session.world.resolve('ruin')
    assert s.ctx.spatial.blocked_by(enemy)==ruin and s.ctx.resources.current(ruin,'hp')==100
    s=proof(s,'gargoyle_actual_blocker');assert not s.ctx.alive(ruin) and s.ctx.resources.current(ruin,'hp')==0
    assert s.ctx.resources.current('foreign','hp')==100
    hit=next(e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['target']==ruin)
    assert hit['payload']['source']==enemy and hit['payload']['ability']=='ability/ch9/dugago/mode0'
    FACTS['gargoyle']={'actual_blocker':ruin,'hit_tick':hit['time'],'ruin_HP_after':0,'foreign_HP':100}
def stone_ground_via_public_stun():
    p=fixture('durokt');p['definitions'] += [
        {'id':'buff/919peer/finite_stun','kind':'buff','duration_seconds':1,'selection_flags':{'abnormal_flags':[0]}},
        {'id':'selector/919peer/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1},
        {'id':'ability/919peer/stun','kind':'ability','activation':{'mode':'manual'},'selector':'selector/919peer/enemy','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/919peer/finite_stun'}}]},
        {'id':'unit/919peer/operator','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':3100,'atk':37,'def':0,'mres':0}},'resources':{'hp':{'role':'health','capacity':3100,'initial':3100}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'abilities':['ability/919peer/stun']}}]
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/919peer/operator','instanceAlias':'operator','position':{'row':6,'col':8}})
    p['scenarioDraft']['commands']=[{'at':1,'action':'skill','source':'operator','ability':'ability/919peer/stun'}]
    s=sim(p);s=proof(s,'durokt_public_ground',150);ruin=s.session.world.resolve('ruin')
    FACTS['stone_diagnostic']={'mode':s.ctx.resources.current('enemy','mode'),'ruin_hp':s.ctx.resources.current(ruin,'hp'),'foreign_hp':s.ctx.resources.current('foreign','hp'),'commands':[thaw(e['payload']) for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']=='ability/919peer/stun'],'accepted':[{'time':e['time'],'payload':thaw(e['payload'])} for e in s.session.events if e['type']=='damage.accepted']}
    FACTS['stone_trajectory']=[{'time':e['time'],'type':e['type'],'payload':thaw(e['payload'])} for e in s.session.events if (e['type']=='resource.changed' and e['payload'].get('resource')=='mode') or (e['type'] in ['ability.started','ability.finished'] and e['payload'].get('source')==s.session.world.resolve('enemy')) or e['type']=='native.durokt.break']
    assert not s.ctx.alive(ruin) and s.ctx.resources.current('foreign','hp')==100
    hit=next(e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['target']==ruin)
    assert hit['payload']['ability']=='ability/ch9/durokt/mode1'
    FACTS['stone']={'public_stun_tick':1,'ground_attack_tick':hit['time'],'ruin_HP_after':s.ctx.resources.current(ruin,'hp')}
def category4_range_and_foreign_exclusion():
    for name in ['dugago','durokt']:
        s=sim(fixture(name,False));assert s.ctx.spatial.select('enemy','selector/ch9/'+name+'/range')==[]
        assert s.ctx.spatial.select('enemy','selector/ch9/'+name+'/blocker')==[];s.advance(40)
        assert s.ctx.resources.current('ruin','hp')==s.ctx.resources.current('foreign','hp')==100
        b=sim(fixture(name));b.advance(1);picked=b.ctx.spatial.select('enemy','selector/ch9/'+name+'/blocker')
        assert picked==[b.session.world.resolve('ruin')] and b.session.world.resolve('foreign') not in picked
def source_vectors_routes_and_cell_profiles():
    scene=DATA['scenarioDraft'];raw=NATIVE['predefines']['tokenInsts'];actual=scene['initialEntities'];assert len(raw)==len(actual)==6
    for i,(a,b) in enumerate(zip(raw,actual)):
        assert b['parameters']['native_instance']==a and b['parameters']['raw_alias']==a['alias']
        assert b['registration_key']=='level_main_09-17/tokenInsts/'+str(i) and b['instanceAlias'] is None
        assert b['position']=={'row':scene['map']['rows']-1-a['position']['row'],'col':a['position']['col']} and b['facing']==a['direction'].lower()
    actions=[a for w in NATIVE['waves'] for f in w['fragments'] for a in f['actions']]
    converted=[a for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions']]
    assert len(actions)==len(converted);births=0;offsets=[]
    for raw,ir in zip(actions,converted):
        assert raw==ir['metadata']['native_action'] and raw['count']==ir['count']
        assert raw['preDelay']==ir['delay_seconds'] and raw['interval']==ir['interval_seconds']
        if ir['kind']!='spawn':continue
        births+=ir['count'];route=NATIVE['routes'][raw['routeIndex']];path=ir['spawn']['route'];assert path['motionMode']==route['motionMode']
        assert path['spawnOffset']==route['spawnOffset'] and path['spawnRandomRange']==route['spawnRandomRange']
        for checkpoint in path.get('checkpoints',[]):
            offset=checkpoint.get('reachOffset',{})
            if any(offset.values()):
                assert path['reach_offset_policy']=={'rule':'rule/m9_checkpoint_cartesian','parameters':{'axis_signs':{'row':-1,'col':1}}};offsets.append(offset)
    assert births==63 and len(NATIVE['routes'])==35 and offsets
    map_=scene['map']
    assert map_['rows']==len(NATIVE['mapData']['map']) and map_['cols']==len(NATIVE['mapData']['map'][0])
    for index,cell in enumerate(map_['tiles']):
        row,col=divmod(index,map_['cols'])
        raw_tile=NATIVE['mapData']['tiles'][NATIVE['mapData']['map'][row][col]]
        assert cell['tileKey']==raw_tile['tileKey'] and cell['blackboard']==raw_tile['blackboard'] and cell['heightType']==raw_tile['heightType']
        assert cell['buildableType']=={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3}[raw_tile['buildableType']] and cell['passableMask']=={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3}[raw_tile['passableMask']]
    cell_profiles=map_.get('tile_cell_mechanics',{});assert cell_profiles=={'3:6':{'type':'occupancy_buff_field','definition':'unit/ch8/environment/infection_field','expected_blackboard':{'damage':180.0,'duration':300.0,'atk':.5,'attack_speed':50.0}}}
    assert len(scene['roster'])==12 and scene['resources']['life']=={'initial':99999,'capacity':99999}
    assert scene['resources']['dp']['initial']==10 and scene['parameters']['deploy_capacity']==9
    FACTS['source']={'births':births,'routes':35,'pillars':6,'offsets':offsets,'fixed12':True,'unit_stats_changed':False}

def main():
    assert implementation_digest()==CORE
    files=[Path(__file__),PACKAGE,SOURCE,ROOT/'tools/chapter09_stage919_assembly_v1/providers_v2.py',ROOT/'tools/chapter09_stage919_assembly_v1/providers.py']
    files += [p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
    before={str(p):sha(p) for p in files};results=[]
    for fn in [source_vectors_routes_and_cell_profiles]:
        try:fn();results.append({'case':fn.__name__,'passed':True})
        except Exception as error:results.append({'case':fn.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    after={str(p):sha(p) for p in files};code=0 if all(x['passed'] for x in results) and before==after else 1
    report={'schema':'ark-sim/independent-source919-review/v1','core_before':CORE,'core_after':implementation_digest(),'actual_exit':code,'results':results,'facts':FACTS,'artifacts':ARTIFACTS,'source_before':before,'source_after':after,'source_equal':before==after,'whole_stage':False}
    path=OUT/'review.cell_source.v5.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
