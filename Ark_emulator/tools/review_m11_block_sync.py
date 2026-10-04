"""Independent actual M11 blocking/cast boundary review, isolated from primary."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
EXPECTED='5b78616b961dbb4d0eda9276be68b8e2b37202b0267878255007921ad7e8712f'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_child(package):
    from ark_sim import Compiler,Engine
    from ark_sim.contracts import thaw
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.compare import first_difference
    from ark_sim.tools.replay import replay
    source=json.loads(Path(package).read_bytes())
    results=[]
    for command_at,expected_starts in [(0,[]),(1,[]),(2,[1])]:
        data=json.loads(Path(package).read_bytes())
        data['scenarioDraft'].update(id='scenario/peer_m11_'+str(command_at),map={'rows':9,'cols':12},waves=[],scheduledEffects=[],objectives={},
            initialEntities=[{'definition':'unit/char_151_myrtle','instanceAlias':'myrtle','position':{'row':4,'col':4},'components':{'resources':{'sp':{'initial':24}}}},
                {'definition':'unit/enemy_1000_gopro','instanceAlias':'enemy','position':{'row':4,'col':4},'route':{'motionMode':'WALK','endPosition':{'row':4,'col':8}}}])
        program=Compiler().compile(data);sim=Engine.create(program)
        sim.submit({'action':'skill','source':'myrtle','ability':'ability/campaign_myrtle_s2'},at=command_at)
        sim.advance(10);restored=Engine.restore(program,sim.checkpoint())
        sim.advance(16);restored.advance(16)
        enemy=sim.session.world.resolve('enemy')
        starts=[e['time'] for e in sim.session.events if e['type']=='ability.started' and e['payload']['source']==enemy]
        assert starts==expected_starts,(command_at,starts)
        damage=[e for e in sim.session.events if e['type']=='damage.accepted' and e['payload']['source']==enemy]
        assert [(e['time'],e['payload']['amount']) for e in damage]==([(19,9.5)] if command_at==2 else [])
        assert not [e for e in sim.session.events if e['type']=='command.rejected']
        assert sim.ctx.spatial.blocked_by(enemy) is None
        own=[e for e in sim.session.events if e['type']=='attack.accepted' and e['payload']['source']==sim.session.world.resolve('myrtle')]
        assert not own, 'Stopped pending normal attack must not hit after S2 activation'
        assert first_difference(sim.snapshot(),restored.snapshot()) is None
        assert first_difference(sim.snapshot(),replay(program,sim.export_replay()).snapshot()) is None
        results.append({'case':'command_'+str(command_at),'result':'passed','independent_expected_enemy_starts':expected_starts,
            'actual_enemy_starts':starts,'program_fingerprint':program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,
            'commands':sim.export_replay()['commands'],'initial_entities':thaw(program.scenario['initialEntities']),
            'events':[thaw(e) for e in sim.session.events if e['type'] in ('command.accepted','blocking.changed','ability.started','ability.interrupted','damage.accepted')],
            'checkpoint_equal':True,'replay_equal':True})
    # A generic capacity modifier, not a Myrtle-specific branch, must release
    # the second real WALK enemy before it can start a cast in that same tick.
    data=json.loads(Path(package).read_bytes())
    data['entities'].append({'id':'unit/m11_peer_blocker','kind':'entity','tags':['player','ground'],
        'components':{'attributes':{'base':{'max_hp':1000,'atk':0,'def':0,'mres':0,'block_count':2}},
            'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'spatial':{},
            'deployable':{'policy':'policy/ark_ground_deploy','terrain':'ground'},'abilities':['ability/m11_peer_lower']}})
    data['buffs'].append({'id':'buff/m11_peer_lower','kind':'buff','modifiers':[{'attribute':'block_count','layer':'flat','value':-1}]})
    data['abilities'].append({'id':'ability/m11_peer_lower','kind':'ability','activation':{'mode':'manual','on_start':[
        {'op':'apply_buff','target':'source','buff':'buff/m11_peer_lower'}]},'timeline':[]})
    initial=[{'definition':'unit/m11_peer_blocker','instanceAlias':'blocker','position':{'row':4,'col':4}}]+[
        {'definition':'unit/enemy_1000_gopro','instanceAlias':'e'+str(i),'position':{'row':4,'col':4},
            'route':{'motionMode':'WALK','endPosition':{'row':4,'col':8}}} for i in range(2)]
    data['scenarioDraft'].update(id='scenario/m11_peer_capacity',map={'rows':9,'cols':12},waves=[],scheduledEffects=[],objectives={},initialEntities=initial)
    program=Compiler().compile(data);sim=Engine.create(program);sim.advance(1)
    blocker=sim.session.world.resolve('blocker');enemies=[sim.session.world.resolve('e'+str(i)) for i in range(2)]
    assert all(sim.ctx.spatial.blocked_by(e)==blocker for e in enemies)
    sim.submit({'action':'skill','source':'blocker','ability':'ability/m11_peer_lower'});sim.advance(1)
    relations=[sim.ctx.spatial.blocked_by(e) for e in enemies];assert relations==[blocker,None],relations
    starts=[e['payload']['source'] for e in sim.session.events if e['type']=='ability.started' and e['payload']['source'] in enemies]
    assert starts==[enemies[0]],starts
    restored=Engine.restore(program,sim.checkpoint());sim.advance(20);restored.advance(20)
    assert first_difference(sim.snapshot(),restored.snapshot()) is None
    assert first_difference(sim.snapshot(),replay(program,sim.export_replay()).snapshot()) is None
    results.append({'case':'generic_capacity2_to1','result':'passed','actual_relations':relations,'enemy_ids':enemies,
        'actual_enemy_cast_sources':starts,'program_fingerprint':program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,
        'commands':sim.export_replay()['commands'],'initial_entities':thaw(program.scenario['initialEntities']),
        'events':[thaw(e) for e in sim.session.events if e['type'] in ('blocking.changed','ability.started','command.accepted')],
        'checkpoint_equal':True,'replay_equal':True})
    return {'passed':True,'implementation_sha256':implementation_digest(),'cases':results,
        'source_no_block':next(b for b in source['buffs'] if b['id']=='buff/campaign_myrtle_no_block'),
        'source_skill':next(a for a in source['abilities'] if a['id']=='ability/campaign_myrtle_s2')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-root',type=Path,default=ROOT.parent/'unpack_work/campaign_m11_block_sync_candidate')
    parser.add_argument('--package',type=Path,default=ROOT/'packages/campaign/mainline_models/level_main_00-10.m11_block_sync.json')
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/m11_block_sync_independent_review.json')
    args=parser.parse_args();candidate=args.candidate_root.resolve();package=args.package.resolve()
    files=[Path(__file__),package,ROOT/'packages/campaign/skills.myrtle.json',ROOT/'tools/probe_c0_myrtle_block_boundary.py']
    before={str(p):sha(p) for p in files}
    script="import sys,json;sys.path.insert(0,sys.argv[1]);import ark_sim;import ark_sim.adapters.api as api;assert api.__file__.startswith(sys.argv[1]);from ark_sim.adapters.api import implementation_digest;assert implementation_digest()==sys.argv[5];sys.path.insert(0,sys.argv[2]);from tools.review_m11_block_sync import run_child;print(json.dumps(run_child(sys.argv[3])))"
    result=subprocess.run([sys.executable,'-c',script,str(candidate),str(ROOT),str(package),'reserved',EXPECTED],cwd=candidate,capture_output=True,text=True)
    after={str(p):sha(p) for p in files};stable=before==after
    if result.returncode:
        record={'passed':False,'error':result.stderr,'stdout':result.stdout,'implementation_sha256':EXPECTED}
    else:record=json.loads(result.stdout)
    record.update(schema='ark-sim/campaign-mechanism-test-evidence/v1',identity_stable=stable,candidate_root=str(candidate),
        input_package=str(package),input_package_sha256=sha(package),source_at_start=before,source_at_completion=after,
        tests=[{'path':'tools/review_m11_block_sync.py','source_sha256':sha(Path(__file__)),'result':'passed' if result.returncode==0 and stable else 'failed'}],
        primary_modified=False,formal_approval=False,review_receipt=False,projection_fix_included=False)
    record['passed']=record['passed'] and stable and record['implementation_sha256']==EXPECTED
    args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':record['passed'],'identity_stable':stable,'cases':len(record.get('cases',[])),'output':str(args.output)}))
    return 0 if record['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
