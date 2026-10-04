from tools.experiments.chapter02_twelve_peer.test_module import *
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
import hashlib
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    core=implementation_digest();out=ROOT/'validation/campaign/chapter02_twelve_peer/taunt_failure';out.mkdir(parents=True,exist_ok=True);rows=[]
    for name in ('enemy_1011_wizard','enemy_1028_mocock'):
        p=block_scene(name);program=Compiler().compile(p);s=Engine.create(program,seed=4819);commands=[{'action':'deploy','entity':'unit/peer/blocker','position':{'row':2,'col':2},'alias':'blocker','at':0}]
        s.submit({k:v for k,v in commands[0].items() if k!='at'},at=0);s.advance(1);blocker=s.ctx.spatial.blocked_by('enemy');assert blocker==s.session.world.resolve('blocker')
        s.advance(40);directory=out/name;directory.mkdir(exist_ok=True)
        for filename,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('final.json',s.snapshot())]:
            (directory/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        rows.append({'native_enemy_id':name,'actual_blocked_by':blocker,'blocker_taunt':0,'other_taunt':20,'expected_targets':[blocker],
            'actual_packets':[thaw(e) for e in s.session.events if e['type']=='damage.accepted'],'other_HP':s.ctx.resources.current('other','hp'),
            'files':{str(path.relative_to(ROOT)):sha(path) for path in directory.iterdir()}})
    assert core==implementation_digest()
    locks=['packages/campaign/chapter02_units/main_02-10.enemies.reference_module.json','tools/build_chapter02_10_enemy_module.py','tools/experiments/chapter02_twelve_peer/test_module.py',str(Path(__file__).relative_to(ROOT))]
    report={'schema':'ark-sim/content-priority-counterexample/v1','status':'actual_declared_block_priority_failure','core_before':core,'core_after':implementation_digest(),
        'source_locks':{x:sha(ROOT/x) for x in locks},'cases':rows,'expectation':'Actual combat INPUT_TARGET2 module declares current blocker first. Finite additive -1e6 does not guarantee this before arbitrary legal taunt.',
        'fixture_error_preserved':'initial.log used scenario instanceAlias for public deploy instead of alias; corrected before runtime target assertions.','client_verified':False,'formal_approved':False}
    (out/'original_failure.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'core':core,'sha256':sha(out/'original_failure.json')}))
if __name__=='__main__':main()
