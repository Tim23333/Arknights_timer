"""Native Sensor/cards short consumer evidence, new runtime identity bound; whole process proof separate."""
import hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'
CORE='1ef9635ee70a8159e0523156aeeb177329d19d12a26185b98b9d9fa55ea3c3d5'
PACKAGE=ROOT/'packages/campaign/chapter03_stage_models/level_main_03-07.m58.reference_model.json'
OUT=ROOT/'validation/campaign/chapter03_stage/03_07_m58_short'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import observations,export_events,write_canonical


def main():
    import ark_sim
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    assert hashlib.sha256(PACKAGE.read_bytes()).hexdigest()=='4195745d994c01503e1666b4f1caec036b1efda71b4030284bd95b74280c5c06'
    guards=[PACKAGE,Path(__file__)];before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards}
    p=json.loads(PACKAGE.read_bytes());scene=p['scenarioDraft'];counts=Counter();controls=Counter()
    for wave in scene['timeline']['waves']:
        for fragment in wave['fragments']:
            for a in fragment['actions']:
                if a['kind']=='spawn':counts[a['spawn']['definition']]+=a.get('count',1)
                else:controls[a['metadata']['native_action']['actionType']]+=a.get('count',1)
    assert sum(counts.values())==61 and len(counts)==9 and controls=={'PREVIEW_CURSOR':2,'DISPLAY_ENEMY_INFO':3}
    assert scene['resources']['crate_cards']=={'initial':5,'capacity':5}
    assert len(scene['roster'])==13 and len(scene['initialEntities'])==1
    native=scene['metadata']['native_predefines'];instance=scene['initialEntities'][0]
    assert instance['parameters']['native_instance']==native['tokenInsts'][0]
    assert instance['position']=={'row':3,'col':3} and instance['facing']=='up'
    program=Compiler().compile(p);s=Engine.create(program,seed=scene['seed'])
    assert s.ctx.resources.current('native_sensor','hp')==100
    tile=s.ctx.spatial.grid.tile(3,3);assert tile['passableMask']==2 and tile['buildableType']==0
    # No unit or wave mutation: native card cost5, finite stock, actual map.
    cells=[(i//12,i%12) for i,t in enumerate(scene['map']['tiles']) if t['buildableType']==1]
    row,col=next(cell for cell in cells if cell!=(3,3))
    commands=[{'at':0,'action':'deploy','definition':'unit/ch3/crate','alias':'native_card','position':{'row':row,'col':col}}]
    s.submit({k:v for k,v in commands[0].items() if k!='at'},at=0);s.advance(40)
    assert s.ctx.resources.current('system/battle','crate_cards')==4 and s.ctx.resources.current('native_card','hp')==100
    assert s.ctx.get('native_card',('selection_state','category'))==4
    assert abs(s.ctx.resources.current('native_sensor','sp')-40/30)<1e-9
    directory=OUT;directory.mkdir(parents=True,exist_ok=True);cp=directory/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin));s.advance(50);r.advance(50)
    actual=observations(s);assert actual==observations(r)==observations(replay(program,s.export_replay()))
    for name,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('snapshot.json',s.snapshot())]:write_canonical(directory/name,value)
    journal=export_events(directory/'events.jsonl',s);after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};assert before==after and implementation_digest()==CORE
    write_canonical(directory/'final_review.json',{'schema':'ark-sim/chapter03-predefine-short/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'births':dict(counts),'controls':dict(controls),'end_tick':90,'observations':actual,'journal':journal,'checkpoint_sha256':pin,
        'durable_checkpoint_equal':True,'replay_equal':True,'known_gaps':p['manifest']['metadata']['pending_model_gaps'],'whole_stage_accepted':False,'actual_client_verified':False,
        'scope':'Actual original3-7 preplaced Sensor HP/SP/UP/terrain, finite nativecrate cards/category4/publicpayment, full short CP/replay; selected source composition input, whole process acceptance separate'})
    print(json.dumps({'passed':True,'end_tick':90,'events':actual['event_count'],'whole_stage_accepted':False}))


if __name__=='__main__':main()
