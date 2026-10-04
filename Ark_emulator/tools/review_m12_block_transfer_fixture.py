"""Independent original/single-blocker diagnosis; no old test/core mutation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT.parent/'unpack_work/campaign_m12_projection_candidate'


def child():
    from ark_sim import Compiler,Engine
    from ark_sim.contracts import thaw
    from ark_sim.adapters.api import implementation_digest
    sys.path.insert(0,str(ROOT/'tests_v2'))
    from test_campaign_acceptance import scene
    cases=[]
    for single in (False,True):
        data=scene(route={'motionMode':'WALK','endPosition':{'row':0,'col':4}})
        data['entities'][0]['components']['abilities']=[];data['entities'][0]['tags']=['enemy']
        blocker=data['entities'][1];blocker['tags']=['player']
        blocker['components']['attributes']['base']['block_count']=1
        blocker['components']['deployable']={'base_cost':0,'cooldown_seconds':0}
        data['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':2}
        if single:data['scenarioDraft']['initialEntities'][2]['position']={'row':0,'col':0}
        data['buffs']=[{'id':'buff/release','kind':'buff','duration_seconds':1,'control':{'block':False}}]
        data['scenarioDraft']['dependencies']=['buff/release']
        sim=Engine.create(Compiler().compile(data));sim.ctx.spatial.blocking()
        old=sim.session.world.resolve('target1');second=sim.session.world.resolve('target2')
        assert sim.ctx.spatial.blocked_by('source')==old
        sim.ctx.buffs.apply('target1','target1','buff/release')
        assert sim.ctx.spatial.blocked_by('source') is None # immediate release really happened
        sim.advance(1);after=sim.ctx.spatial.blocked_by('source')
        assert after==(None if single else second),(single,after)
        position=sim.ctx.get('source',('spatial','position'))
        distance=abs(position['col']-(0 if single else 3))
        path=sim.ctx.get('source',('spatial','movement_path'),[])
        cases.append({'single_blocker_isolated':single,'old_blocker':old,'second_blocker':second,'blocked_after_tick':after,
            'source_position':position,'distance_to_second':distance,'declared_radius':1,'remaining_path':path,
            'fixture_initial_entities':thaw(sim.program.scenario['initialEntities']),
            'events':[thaw(e) for e in sim.session.events if e['type'] in ('blocking.changed','movement.traveled','buff.applied')]})
    return {'passed':True,'implementation_sha256':implementation_digest(),'cases':cases,
        'diagnosis':'original fixture contains two player/block1/deployable instances of shared unit/target; legal transfer differs from release failure',
        'direct_domain_api_diagnostic_only':True,'command_replay_claim':False,'existing_tests_modified':False,'formal_approval':False}


if __name__=='__main__':
    script="import sys,json;sys.path.insert(0,sys.argv[1]);import ark_sim;sys.path.insert(0,sys.argv[2]);from tools.review_m12_block_transfer_fixture import child;print(json.dumps(child()))"
    run=subprocess.run([sys.executable,'-c',script,str(CANDIDATE),str(ROOT)],cwd=CANDIDATE,capture_output=True,text=True)
    if run.returncode:raise RuntimeError(run.stderr)
    value=json.loads(run.stdout);value['source_test_sha256']=hashlib.sha256((ROOT/'tests_v2/test_activation_control_review.py').read_bytes()).hexdigest()
    output=ROOT/'validation/campaign/m12_block_transfer_fixture_independent_review.json'
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':value['passed'],'relations':[c['blocked_after_tick'] for c in value['cases']],'output':str(output)}))
