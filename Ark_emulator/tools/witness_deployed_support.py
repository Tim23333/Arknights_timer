"""Current-package A/D/F extensions; independent values, recorded commands only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import witness_deployed_six as six
PACKAGE=Path(os.environ.get('CAMPAIGN_DEPLOYED_SUPPORT_PACKAGE',str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')))


def scene(initial,enemies=(),patients=()):
    six.PACKAGE=PACKAGE # Input selection only; frozen helper source is unchanged.
    return six.scene(initial,enemies,patients)


def make(data):return six.make(data)
def cmd(sim,source,ability,at=0):return six.command(sim,source,ability,at)
def finish(sim,expected):return six.finish(sim,expected)
def events(sim,kind,source=None,ability=None):return six.events(sim,kind,source,ability)
def eq(actual,expected):return six.eq(actual,expected)


def add_probe(data,atk=1000):
    data['entities'].append({'id':'unit/support_endpoint_probe','kind':'entity','tags':['player'],
        'components':{'attributes':{'base':{'atk':atk}},'spatial':{},
            'abilities':['ability/support_probe_'+k for k in ('arts','physical','true')]}})
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/support_endpoint_probe','instanceAlias':'probe','position':{'row':0,'col':0}})
    data['selectors'].append({'id':'selector/support_probe_enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1})
    for kind in ('arts','physical','true'):
        data['abilities'].append({'id':'ability/support_probe_'+kind,'kind':'ability','activation':{'mode':'manual'},
            'selector':'selector/support_probe_enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':kind,'scale':.1}}]})


def case_myrtle_vanguard_regen_and_source_exit():
    data=scene([six.actor('myrtle',hp=100),six.actor('bpipe',hp=100,col=5)])
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/char_010_chen','instanceAlias':'chen','position':{'row':5,'col':4},'components':{'resources':{'hp':{'initial':100}}}})
    sim=make(data);sim.advance(31)
    eq(sim.ctx.resources.current('myrtle','hp'),125);eq(sim.ctx.resources.current('bpipe','hp'),125);eq(sim.ctx.resources.current('chen','hp'),100)
    pulses=events(sim,'regeneration.accepted');assert [e['time'] for e in pulses]==[t for t in range(1,31) for _ in range(2)]
    for pulse in pulses:eq(pulse['payload']['amount'],25/30)
    sim.submit({'action':'withdraw','source':'myrtle'});sim.advance(31)
    eq(sim.ctx.resources.current('bpipe','hp'),125)
    return finish(sim,{'vanguard_continuous25_per_sec_30_quantum_pulses':True,'non_vanguard_no_regen':True,'source_exit_stops_next_pulse':True})


def case_plosis_time_event_highest_and_source_exit():
    data=scene([six.actor('plosis',0),six.actor('myrtle',0,col=5)])
    data['scenarioDraft']['initialEntities'] += [
        {'definition':'unit/char_358_lisa','instanceAlias':'suzu','position':{'row':5,'col':4},'components':{'resources':{'sp':{'initial':0}}}},
        {'definition':'unit/char_107_liskam','instanceAlias':'lisk','position':{'row':5,'col':5},'components':{'resources':{'sp':{'initial':0}}}}]
    sim=make(data);sim.advance(30)
    eq(sim.ctx.resources.current('plosis','sp'),1.3);eq(sim.ctx.resources.current('myrtle','sp'),6+1.3)
    eq(sim.ctx.resources.current('suzu','sp'),1.4);eq(sim.ctx.resources.current('lisk','sp'),0)
    sim.submit({'action':'withdraw','source':'plosis'});sim.advance(30)
    eq(sim.ctx.resources.current('myrtle','sp'),6+2.3);eq(sim.ctx.resources.current('suzu','sp'),2.8);eq(sim.ctx.resources.current('lisk','sp'),0)
    return finish(sim,{'deck_Bagpipe_initialSP6_preserved':True,'TIME_plus_plosis1.3':True,'SUPPORT_highest1.4_not1.7':True,'eventSP0':True,'withdraw_restores_only_time_base':True})


def case_plosis_forty_second_mode_and_late_packet_gate():
    sim=make(scene([six.actor('plosis',100)],patients=[(4,5)]));cmd(sim,'plosis','ability/plosis_s2_first_packet')
    sim.advance(1235)
    heals=events(sim,'healing.accepted','plosis')
    skill=[e for e in heals if e['time']<1200]
    assert [e['time'] for e in skill]==[7+23*i for i in range(52)]
    assert all(e['payload']['amount']==382 for e in heals)
    assert [e['time'] for e in heals if e['time']>=1200]==[1234]
    assert sim.ctx.resources.current('plosis','mode')==0
    # One second-period quantum completes after the manual cast ends; highest
    # self aura .3 applies only when that recovery is no longer frozen.
    eq(sim.ctx.resources.current('plosis','sp'),1.3)
    return finish(sim,{'duration1200':True,'skill_last1180':True,'old_mode_packet1203_suppressed':True,'normal_restore1234':True,'normal_ATK382':True,'SP_resume1.3':True})


def case_saria_five_layers_atk_and_actual_defense():
    # Saria's native normal range is the origin cell; the synthetic enemy is
    # colocated rather than incorrectly borrowing the ranged skill footprint.
    data=scene([six.actor('demkni')],enemies=[(4,4)])
    enemy=next(e for e in data['entities'] if e['id']=='unit/deployed_witness_enemy')
    enemy['components']['attributes']['base'].update(atk=2000,max_hp=1000000000)
    enemy['components']['resources']['hp'].update(initial=1000000000,capacity=1000000000)
    enemy['components']['abilities']=['ability/saria_probe_incoming']
    data['selectors'].append({'id':'selector/saria_probe_receiver','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
    data['abilities'].append({'id':'ability/saria_probe_incoming','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/saria_probe_receiver','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical'}}]})
    sim=make(data);cmd(sim,'enemy0','ability/saria_probe_incoming',at=3000);sim.advance(3006)
    hits=events(sim,'damage.accepted','demkni','ability/char_202_demkni/normal_attack')
    by_tick={e['time']:e['payload']['amount'] for e in hits}
    eq(by_tick[17],513-50);eq(by_tick[629],513*1.05-50);eq(by_tick[3005],513*1.25-50)
    incoming=events(sim,'damage.accepted','enemy0','ability/saria_probe_incoming')
    assert len(incoming)==1 and incoming[0]['time']==3000;eq(incoming[0]['payload']['amount'],2000-631*1.2)
    eq(sim.ctx.resources.current('demkni','hp'),2952-(2000-631*1.2))
    return finish(sim,{'five20s_steps_ATK641.25_DEF757.2':True,'actual_incoming1242.8':True,'atk_packet17_629_3005':True})


def case_saria_arts_only_and_source_exit():
    data=scene([six.actor('demkni',80)],enemies=[(4,5)]);add_probe(data)
    sim=make(data);cmd(sim,'demkni','ability/demkni_s3')
    for t,kind in [(1,'arts'),(3,'physical'),(5,'true')]:cmd(sim,'probe','ability/support_probe_'+kind,t)
    sim.submit({'action':'withdraw','source':'demkni'},at=7);cmd(sim,'probe','ability/support_probe_arts',9);sim.advance(10)
    hits=events(sim,'damage.accepted','probe')
    assert [e['time'] for e in hits]==[1,3,5,9]
    for e,value in zip(hits,[155,50,100,100]):eq(e['payload']['amount'],value)
    return finish(sim,{'arts155_physical50_true100':True,'source_exit_arts100':True})


def case_saria_recipient_emission_freeze_same_frame_finish():
    data=scene([six.actor('demkni',80)])
    data['entities'].append({'id':'unit/support_hold','kind':'entity','tags':['player'],
        'components':{'attributes':{'base':{'max_hp':10000}},'spatial':{},
            'resources':{'hp':{'initial':100,'capacity':10000,'role':'health'},'sp':{'initial':0,'capacity':100,'parameters':{'freeze_while_cast':True,'freeze_cast_modes':['manual']}}},
            'abilities':['ability/support_hold']}})
    data['abilities'].append({'id':'ability/support_hold','kind':'ability','activation':{'mode':'manual'},'duration_seconds':16/30,'timeline':[]})
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/support_hold','instanceAlias':'held','position':{'row':4,'col':5}})
    sim=make(data)
    cmd(sim,'demkni','ability/demkni_s3');cmd(sim,'held','ability/support_hold');sim.advance(17)
    heals=events(sim,'healing.accepted','demkni');assert len(heals)==1 and heals[0]['time']==16;eq(heals[0]['payload']['amount'],179.55)
    ended=events(sim,'ability.finished','held');assert len(ended)==1 and ended[0]['time']==16
    assert heals[0]['id']<ended[0]['id']
    eq(sim.ctx.resources.current('held','sp'),0)
    return finish(sim,{'accepted_heal16_before_manual_finish16':True,'emission_frozen_SP0_after_finish':True})


def case_canonical_regeneration_does_not_return_saria_sp():
    data=scene([six.actor('demkni'),six.actor('myrtle',0,hp=100,col=5)])
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/char_358_lisa','instanceAlias':'suzu','position':{'row':5,'col':4},'components':{'resources':{'sp':{'initial':70}}}})
    sim=make(data);cmd(sim,'suzu','ability/lisa_s3');sim.advance(31)
    regen=events(sim,'regeneration.accepted');assert regen
    assert not events(sim,'healing.accepted')
    # Myrtle's25 HP/s plus Suzuran115.2 regeneration raises HP but cannot create
    # Saria's accepted-heal event. Fixed deck also grants initialSP6; the normal
    # TIME driver first completes29, so only one additional base recovery1.
    eq(sim.ctx.resources.current('myrtle','sp'),7)
    target=sim.session.world.resolve('myrtle')
    gains=[e for e in events(sim,'resource.changed') if e['payload']['resource']=='sp' and e['payload']['target']==target and e['payload']['delta']>0]
    assert [(e['time'],e['payload']['delta']) for e in gains]==[(0,6),(29,1)]
    return finish(sim,{'regeneration_not_healing':True,'initial_deck6_plus_only_TIME_SP1_at29':True,'no_Saria_SP_grant':True})


CASES={name[5:]:fn for name,fn in list(globals().items()) if name.startswith('case_') and callable(fn)}


def run_case(name):
    try:record={'case':name,'result':'passed','actual':CASES[name]()}
    except Exception as error:
        from ark_sim.contracts import thaw
        record={'case':name,'result':'failed','error':repr(error)}
        if six.LAST_SIM is not None:
            record['observed_events']=[thaw(e) for e in six.LAST_SIM.session.events if e['type'] in
                ('damage.accepted','healing.accepted','regeneration.accepted','resource.changed','ability.started','command.rejected')]
        output=os.environ.get('DEPLOYED_SUPPORT_CASE_RESULTS')
        if output:
            with open(output,'a',encoding='utf8') as stream:stream.write(json.dumps(record)+'\n')
        raise
    output=os.environ.get('DEPLOYED_SUPPORT_CASE_RESULTS')
    if output:
        with open(output,'a',encoding='utf8') as stream:stream.write(json.dumps(record)+'\n')
    return record


def main():
    global PACKAGE
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,default=ROOT.parent/'unpack_work/campaign_m12_projection_candidate')
    parser.add_argument('--package',type=Path,default=PACKAGE)
    parser.add_argument('--case',action='append',choices=list(CASES))
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/deployed_support_m12_extended.json')
    args=parser.parse_args();PACKAGE=args.package.resolve();runtime=args.runtime_root.resolve()
    selected=args.case or list(CASES);test=ROOT/'tools/experiments/deployed_support/tests/test_canonical_support.py'
    sources=[ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/skills.myrtle.json',ROOT/'packages/campaign/skills.plosis.json',ROOT/'packages/campaign/skills.demkni.json',ROOT/'packages/campaign/talents.support.json',ROOT/'packages/campaign/talents.attack.json']
    files=[PACKAGE,test,Path(__file__),ROOT/'tools/witness_deployed_six.py',*sources]
    before={str(p):six.sha(p) for p in files}
    digest_code="import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())"
    core_before=subprocess.check_output([sys.executable,'-c',digest_code,str(runtime)],cwd=runtime,text=True).strip()
    code="import sys;sys.path.insert(0,sys.argv[1]);import ark_sim;import ark_sim.adapters.api as api;assert api.__file__.startswith(sys.argv[1]);assert api.implementation_digest()==sys.argv[4];sys.path.insert(0,sys.argv[2]);import pytest;raise SystemExit(pytest.main(sys.argv[5:]))"
    expected='bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'
    assert core_before==expected
    with tempfile.TemporaryDirectory(prefix='ark_support_extended_') as directory:
        path=Path(directory)/'cases.jsonl'
        env=dict(os.environ,CAMPAIGN_DEPLOYED_SUPPORT_PACKAGE=str(PACKAGE),DEPLOYED_SUPPORT_CASE_RESULTS=str(path))
        nodes=[str(test)+'::test_canonical_extension['+name+']' for name in selected]
        process=subprocess.run([sys.executable,'-c',code,str(runtime),str(ROOT),'reserved',expected,*nodes,'-q','--tb=short'],cwd=runtime,env=env,capture_output=True,text=True)
        records=[json.loads(line) for line in path.read_text(encoding='utf8').splitlines()] if path.exists() else []
    after={str(p):six.sha(p) for p in files}
    core_after=subprocess.check_output([sys.executable,'-c',digest_code,str(runtime)],cwd=runtime,text=True).strip()
    stable=before==after and core_before==core_after
    passed=stable and process.returncode==0 and len(records)==len(selected) and all(r['result']=='passed' for r in records)
    value={'schema':'ark-sim/campaign-mechanism-test-evidence/v1','passed':passed,'implementation_sha256':expected,'runtime_root':str(runtime),
        'input_package':str(PACKAGE),'input_package_sha256':six.sha(PACKAGE),'identity_stable':stable,'source_at_start':before,'source_at_completion':after,
        'implementation_at_start':core_before,'implementation_at_completion':core_after,
        'selected_cases':selected,'cases':records,'pytest_output':process.stdout+process.stderr,'pytest_exit_code':process.returncode,
        'tests':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'source_sha256':six.sha(p),'result':'passed' if passed else 'failed'} for p in files[1:4]],
        'scope':'A/D/F canonical extensions only','formal_approval':False,'review_receipt':False,'client_pending_preserved':True}
    args.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':passed,'cases':len(records),'output':str(args.output)}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
