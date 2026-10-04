"""Independent exact-node controls/ack proof, not audiovisual rendering proof."""
import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_chapter08_joint_v4_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
CORE='20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30';MODULE=ROOT/'packages/campaign/chapter08_stage_controls/controls.module.v1.json';SOURCE=MODULE.parent/'source/story_opera.source.v1.json';OUT=ROOT/'validation/campaign/chapter08_controls_independent_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def package(case):
    p=json.loads(MODULE.read_bytes());actions=[]
    keys=['blast_effect_x','blast_effect_x'] if case=='same_key_concurrent' else ['blast_effect_x','blast_effect_y']
    if case.startswith('story'):keys=['story']
    for i,key in enumerate(keys):actions.append({'kind':'control','definition':'control/ch8/source/story/main_08-17' if key=='story' else 'control/ch8/source/opera/'+key,'instanceAlias':'peer_story' if key=='story' else 'peer_'+str(i),'delay_seconds':0 if i==0 else .1,'count':1,'interval_seconds':0,'managed':True,'blocks_wave':True,'blocks_fragment':False})
    p['entities']=[{'id':'unit/independent/control_sentinel','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':1555,'atk':21,'def':33,'mres':17}},'resources':{'hp':{'initial':1555,'capacity':1555,'role':'health'},'sp':{'initial':9,'capacity':15}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
    p['scenarioDraft']={'id':'scene/independent/controls/'+case,'ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':3},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'sentinel','position':{'row':0,'col':1}}],
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':actions}]}]}}
    if case=='story_public_acks':p['scenarioDraft']['commands']=[{'at':2,'action':'control_ack','control':'peer_story','step':999}]+[{'at':3*(i+1),'action':'control_ack','control':'peer_story','step':2*i+1} for i in range(8)]
    return p
def domain(s):return {'world':s.session.world.snapshot(),'tasks':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def run(case):
    p=package(case);program=Compiler().compile(p);s=Engine.create(program,seed=101808);initial_rng=s.session.random.snapshot();folder=OUT/case;folder.mkdir(parents=True,exist_ok=True);boundary=10;end=105
    s.session.advance(boundary);cp=folder/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin));s.session.advance(end-boundary);r.session.advance(end-boundary);head=replay(program,s.export_replay())
    assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
    assert s.session.random.snapshot()==initial_rng and s.ctx.resources.current('sentinel','hp')==1555 and s.ctx.resources.current('sentinel','sp')==9
    source=json.loads(SOURCE.read_bytes());events=[thaw(e) for e in s.session.events];nodes=[e for e in events if e['type']=='source.opera.node.observed'];done=[e for e in events if e['type']=='source.opera.completed']
    if not case.startswith('story'):
        assert len(nodes)==6 and sorted(e['time'] for e in done)==[90,93]
        assert sorted((e['time'],e['payload']['node_index']) for e in nodes)==[(0,1),(3,1),(6,2),(9,0),(9,2),(12,0)]
        for e in nodes:assert e['payload']['source_node']==source['opera']['commands'][e['payload']['key']]['parsed_nodes'][e['payload']['node_index']]
    popup=[e for e in events if e['type']=='source.story.popup.observed'];acks=[e for e in events if e['type']=='control.acknowledged'];completed=[e for e in events if e['type']=='control.completed']
    if case=='story_public_acks':
        assert [e['time'] for e in popup]==[0,3,6,9,12,15,18,21] and [e['time'] for e in acks]==[3,6,9,12,15,18,21,24]
        assert all(e['payload']['automatic'] is False for e in acks)
        assert [e['time'] for e in completed]==[33] and len([e for e in events if e['type']=='command.rejected'])==1
        expected=[v for v in source['story']['commands'] if v['command']=='PopupDialog'];assert [e['payload']['raw_command'] for e in popup]==expected
    if case=='story_without_ack':assert len(popup)==1 and not acks and not completed and s.ctx.controls.instance('peer_story')['phase']=='awaiting_ack'
    (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
    with (folder/'events.jsonl').open('wb') as f:
        for e in events:f.write((json.dumps(e,ensure_ascii=False)+'\n').encode())
    return {'case':case,'CP':True,'head':True,'all_events':True,'battle_rng_unchanged':True,'HP1555_SP9_unchanged':True,'node_times':[(e['time'],e['payload']['key'],e['payload']['node_index']) for e in nodes],'opera_completion_times':[e['time'] for e in done],'source_popup_times':[e['time'] for e in popup],'actual_external_ack_times':[e['time'] for e in acks],'control_completion_times':[e['time'] for e in completed],'files':{str(q):sha(q) for q in folder.iterdir()}}
def main():
    assert implementation_digest()==CORE and sha(MODULE)=='aad91ae8effb4fc75b1ea2af80c95aa371d9b3bf20ebf37d931f5477b062f1b5';before=sha(MODULE);OUT.mkdir(exist_ok=True);rows=[run(case) for case in ('same_key_concurrent','xy_concurrent','story_public_acks','story_without_ack')]
    assert sha(MODULE)==before and implementation_digest()==CORE
    out=OUT/'report.json';assert not out.exists();out.write_bytes((json.dumps({'status':'four_fresh_source_control_policy_cases_passed','core':CORE,'module_sha256':before,'source_sha256':sha(SOURCE),'rows':rows,'scope':'Typed AV scheduling and real external acknowledgements/logical clock policy; no actual renderer/native pause/global-lock proof or whole stage.'},ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()
