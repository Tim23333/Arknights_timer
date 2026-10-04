"""Actual Faust branch activates source ballista and its own SP fires a real arrow."""
import json
from copy import deepcopy
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim.contracts import thaw
ROOT=Path(__file__).resolve().parents[3]
CAPTURES=[]


def fixture():
    stage=json.loads((ROOT/'packages/campaign/chapter05_stage_models/combined_v3/level_main_05-10.life99999.json').read_bytes())
    scene=stage['scenarioDraft'];scene.pop('timeline');scene['waves']=[];scene['objectives']={}
    scene['initialEntities'].append({'definition':'unit/ch5/faust/level0','instanceAlias':'faust',
        'position':{'row':0,'col':0}})
    stage['definitions'].append({'id':'unit/chain_guard','kind':'entity','tags':['player'],'components':{
        'attributes':{'base':{'max_hp':100000,'atk':0,'def':100,'mres':0,'block_count':0}},
        'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},
        'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    scene['initialEntities'].append({'definition':'unit/chain_guard','instanceAlias':'guard',
        'position':{'row':4,'col':9}})
    return stage


def test_source_faust450_branch477_real_ballista_later_charge_and_shot_disk_replay(tmp_path):
    p=fixture();s=Engine.create(Compiler().compile(p),seed=5510);s.advance(476)
    assert not s.ctx.active('trap_007_ballis#1')
    assert s.ctx.resources.current('trap_007_ballis#1','sp')==0
    checkpoint=ROOT/'validation/campaign/chapter05_ballista_joint_v3_v2/source_chain.author_v2.pending_branch.checkpoint.json'
    if checkpoint.exists():raise FileExistsError('Preserve actual source-chain checkpoint')
    pin=write_ordered(checkpoint,s.checkpoint())
    r=Engine.restore(s.program,load_bound(checkpoint,pin));s.advance(210);r.advance(210)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    ballista=s.session.world.resolve('trap_007_ballis#1')
    activation=[e for e in s.session.events if e['type']=='entity.activated']
    assert len(activation)==1 and activation[0]['time']==477 and activation[0]['payload']['target']==ballista
    costs=[e for e in s.session.events if e['type']=='resource.changed' and e['payload'].get('source')==ballista and e['payload'].get('reason')=='ability_cost']
    assert len(costs)==1 and costs[0]['payload']['delta']==-5
    shots=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==ballista]
    assert len(shots)==1 and shots[0]['payload']['target']==s.session.world.resolve('guard') and shots[0]['payload']['amount']==500
    assert all(not s.ctx.active('trap_007_ballis#'+str(i)) for i in range(2,11))
    assert len([e for e in s.session.world.entities() if e['definition_id']=='unit/ch5/ballista/source_level6'])==10
    CAPTURES.append({'actual_input':p,'checkpoint_path':str(checkpoint),'checkpoint_sha':pin,'snapshot':s.snapshot(),'events':thaw(tuple(s.session.events)),
        'replay_record':s.export_replay(),'disk_checkpoint_and_replay_equal':True})
