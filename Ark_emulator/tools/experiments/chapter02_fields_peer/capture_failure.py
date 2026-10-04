from tools.experiments.chapter02_fields_peer.test_fields import *
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    before=implementation_digest();p=fixture();weedy=load('skills.weedy.json');r=next(r for r in weedy['rules'] if r['id']=='rule/campaign_weedy_distance_damage');p['rules'].append(deepcopy(r))
    p['abilities'][0]['activation']['on_start'][0]={'op':'damage','damage_type':'true','distance':.5,'parameters':{'value':1200,'per_distance':1},'rules':{'damage.pipeline':r['id']}}
    program=Compiler().compile(p);s=Engine.create(program,seed=4212);commands=[{'action':'skill','source':'caster','ability':'ability/hit','at':0}]
    s.submit({k:v for k,v in commands[0].items() if k!='at'},at=0);s.advance(1)
    out=ROOT/'validation/campaign/chapter02_fields_peer';out.mkdir(exist_ok=True)
    for name,value in [('weedy_input.json',p),('weedy_commands.json',commands),('weedy_snapshot.json',s.snapshot()),('weedy_replay.json',s.export_replay())]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    after=implementation_digest();assert before==after
    locks=['tools/build_chapter02_tile_fields.py','packages/campaign/chapter02_tiles/fields.reference_model.json','packages/campaign/chapter02_tiles/buffs.motion_state.partial.json','packages/campaign/chapter02_tiles/source.reference.json','packages/campaign/skills.weedy.json',str(Path(__file__).relative_to(ROOT)),'tools/experiments/chapter02_fields_peer/test_fields.py']
    rejection=[thaw(e) for e in s.session.events if e['type']=='command.rejected']
    report={'schema':'ark-sim/independent-content-counterexample/v1','status':'actual_declared_composition_gap','actual_core_before':before,'actual_core_after':after,
        'actual_module':sys.modules['ark_sim'].__file__,'source_locks':{x:sha(ROOT/x) for x in locks},'input_sha256':sha(out/'weedy_input.json'),
        'commands_sha256':sha(out/'weedy_commands.json'),'initial_target_HP':5000,'expected_damage_from_exact_Weedy_rule':.5*1200/1,
        'expected_target_HP':4400,'actual_target_HP':s.ctx.resources.current('enemy','hp'),'command_rejection':rejection,
        'reason':'Gazebo before-hook assumes ATK/DEF/RES input bindings absent in this actual selected Weedy distance pipeline, then reconstructs a request without parameters/distance.',
        'model_vs_client':'Expectation comes from literal selected pure rule. Native true-damage gazebo applicability remains separate pending source/body/feedback.',
        'target_content_mutated':False,'formal_approved':False}
    (out/'weedy_distance_original_failure.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'core':before,'report_sha256':sha(out/'weedy_distance_original_failure.json'),'actual_HP':report['actual_target_HP'],'expected_HP':report['expected_target_HP']}))
if __name__=='__main__':main()
