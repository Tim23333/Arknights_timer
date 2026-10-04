"""Independent half-up geometry boundary review in isolated M12 runtime."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
EXPECTED='bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review(package):
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    from ark_sim.tools.compare import first_difference
    from ark_sim.tools.replay import replay
    results=[]
    # Expectations come from transforming integer offsets then floor(x+.5),
    # independent of the candidate's projection function.
    poses=[('target_half',{'row':4,'col':4},{'row':4.5,'col':5},'right'),
        ('target_other_half',{'row':4,'col':4},{'row':5.5,'col':5},'right'),
        ('source_half',{'row':4.5,'col':4},{'row':5,'col':5},'right'),
        ('rotated_source_half',{'row':4.5,'col':4.5},{'row':4,'col':5},'up'),
        ('negative_half_border',{'row':-.5,'col':4},{'row':0,'col':5},'right')]
    for name,origin,target,facing in poses:
        data=json.loads(Path(package).read_bytes())
        data['scenarioDraft'].update(id='scenario/m12_peer_'+name,map={'rows':9,'cols':12},waves=[],scheduledEffects=[],objectives={},
            initialEntities=[{'definition':'unit/char_151_myrtle','instanceAlias':'myrtle','position':origin,'facing':facing},
                {'definition':'unit/enemy_1000_gopro','instanceAlias':'enemy','position':target}])
        offset=(0,1) if facing=='right' else (-1,0)
        cells={(math.floor(origin['row']+.5),math.floor(origin['col']+.5)),
            (math.floor(origin['row']+offset[0]+.5),math.floor(origin['col']+offset[1]+.5))}
        target_cell=(math.floor(target['row']+.5),math.floor(target['col']+.5));expected=target_cell in cells
        program=Compiler().compile(data);sim=Engine.create(program);sim.advance(16)
        attacks=[e for e in sim.session.events if e['type']=='attack.accepted' and e['payload']['source']==sim.session.world.resolve('myrtle')]
        assert len(attacks)==int(expected),(name,len(attacks),expected)
        if expected:assert attacks[0]['time']==15
        assert sim.ctx.spatial.grid._cell(target)==target_cell
        restored=Engine.restore(program,sim.checkpoint());sim.advance(2);restored.advance(2)
        assert first_difference(sim.snapshot(),restored.snapshot()) is None
        assert first_difference(sim.snapshot(),replay(program,sim.export_replay()).snapshot()) is None
        results.append({'case':name,'result':'passed','source':origin,'target':target,'facing':facing,
            'independent_cells':[list(c) for c in sorted(cells)],'expected_target_cell':list(target_cell),'expected_attack_count':int(expected),
            'actual_attack_events':[thaw(e) for e in attacks],'program_fingerprint':program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,
            'checkpoint_equal':True,'replay_equal':True})
    outside=json.loads(Path(package).read_bytes())
    outside['scenarioDraft'].update(map={'rows':9,'cols':12},waves=[],scheduledEffects=[],objectives={},
        initialEntities=[{'definition':'unit/char_151_myrtle','instanceAlias':'myrtle','position':{'row':-.500001,'col':4}}])
    try:Compiler().compile(outside)
    except Exception as error:message=str(error)
    else:raise AssertionError('negative outside half-up border must reject before Engine')
    results.append({'case':'outside_negative_border','result':'passed','independent_cell':[-1,4],'actual_compile_error':message})
    # Circle probes retain true continuous distance, not snapped grid distance.
    circle=json.loads(Path(package).read_bytes())
    circle['entities'].append({'id':'unit/m12_circle_probe','kind':'entity','tags':['player'],
        'components':{'attributes':{'base':{'atk':100}},'spatial':{},'abilities':['ability/m12_circle_probe']}})
    circle['selectors'].append({'id':'selector/m12_circle_probe','kind':'selector','region':{'type':'radius','radius':.2},
        'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1})
    circle['abilities'].append({'id':'ability/m12_circle_probe','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/m12_circle_probe','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true'}}]})
    circle['scenarioDraft'].update(map={'rows':9,'cols':12},waves=[],scheduledEffects=[],objectives={},initialEntities=[
        {'definition':'unit/m12_circle_probe','instanceAlias':'source','position':{'row':4.49,'col':4.49}},
        {'definition':'unit/enemy_1000_gopro','instanceAlias':'enemy','position':{'row':4.6,'col':4.6}}])
    distance=math.hypot(.11,.11);assert distance<.2
    program=Compiler().compile(circle);sim=Engine.create(program)
    sim.submit({'action':'skill','source':'source','ability':'ability/m12_circle_probe'});sim.advance(1)
    damage=[e for e in sim.session.events if e['type']=='damage.accepted'];assert len(damage)==1 and damage[0]['payload']['amount']==100
    assert first_difference(sim.snapshot(),replay(program,sim.export_replay()).snapshot()) is None
    results.append({'case':'continuous_circle','result':'passed','independent_distance':distance,'grid_cells_would_differ':True,'amount':100,'replay_equal':True})
    # The explicit own-blocked exception remains valid even when half-up cells
    # place the stopped enemy outside the geometric horizontal attack row.
    blocked=json.loads(Path(package).read_bytes())
    blocked['scenarioDraft'].update(map={'rows':9,'cols':12},waves=[],scheduledEffects=[],objectives={},initialEntities=[
        {'definition':'unit/char_151_myrtle','instanceAlias':'myrtle','position':{'row':4.5,'col':4}},
        {'definition':'unit/enemy_1000_gopro','instanceAlias':'enemy','position':{'row':4.49,'col':4.49},
            'route':{'motionMode':'WALK','endPosition':{'row':5,'col':4}}}])
    program=Compiler().compile(blocked);sim=Engine.create(program);sim.advance(1)
    caster=sim.session.world.resolve('myrtle');enemy=sim.session.world.resolve('enemy')
    assert sim.ctx.spatial.blocked_by(enemy)==caster
    assert sim.ctx.spatial.grid._cell(sim.ctx.get(enemy,('spatial','position')))==(4,4)
    assert sim.ctx.spatial.grid._cell(sim.ctx.get(caster,('spatial','position')))==(5,4)
    restored=Engine.restore(program,sim.checkpoint());sim.advance(17);restored.advance(17)
    attacks=[e for e in sim.session.events if e['type']=='attack.accepted' and e['payload']['source']==caster]
    assert len(attacks)==1 and attacks[0]['time']==16 and attacks[0]['payload']['target']==enemy
    assert first_difference(sim.snapshot(),restored.snapshot()) is None
    assert first_difference(sim.snapshot(),replay(program,sim.export_replay()).snapshot()) is None
    results.append({'case':'own_blocked_cross_cell_exception','result':'passed','caster_cell':[5,4],'enemy_cell':[4,4],
        'actual_blocked_by':caster,'actual_attack_event':thaw(attacks[0]),'checkpoint_equal':True,'replay_equal':True})
    return {'passed':True,'implementation_sha256':implementation_digest(),'cases':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-root',type=Path,default=ROOT.parent/'unpack_work/campaign_m12_projection_candidate')
    parser.add_argument('--package',type=Path,default=ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/m12_projection_independent_review.json')
    args=parser.parse_args();candidate=args.candidate_root.resolve();package=args.package.resolve()
    files=[Path(__file__),package,ROOT/'tools/probe_c0_corner_projection.py'];before={str(p):sha(p) for p in files}
    code="import sys,json;sys.path.insert(0,sys.argv[1]);import ark_sim;import ark_sim.adapters.api as api;assert api.__file__.startswith(sys.argv[1]);assert api.implementation_digest()==sys.argv[4];sys.path.insert(0,sys.argv[2]);from tools.review_m12_projection import review;print(json.dumps(review(sys.argv[3])))"
    process=subprocess.run([sys.executable,'-c',code,str(candidate),str(ROOT),str(package),EXPECTED],cwd=candidate,capture_output=True,text=True)
    after={str(p):sha(p) for p in files};stable=before==after
    result=json.loads(process.stdout) if process.returncode==0 else {'passed':False,'implementation_sha256':EXPECTED,'error':process.stderr,'stdout':process.stdout}
    result.update(schema='ark-sim/campaign-mechanism-test-evidence/v1',candidate_root=str(candidate),identity_stable=stable,
        source_at_start=before,source_at_completion=after,input_package=str(package),input_package_sha256=sha(package),
        tests=[{'path':'tools/review_m12_projection.py','source_sha256':sha(Path(__file__)),'result':'passed' if process.returncode==0 and stable else 'failed'}],
        primary_modified=False,formal_approval=False,review_receipt=False)
    result['passed']=result['passed'] and stable and result['implementation_sha256']==EXPECTED
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':result['passed'],'cases':len(result.get('cases',[])),'output':str(args.output)}))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
