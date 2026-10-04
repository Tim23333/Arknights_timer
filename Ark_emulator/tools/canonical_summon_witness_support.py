"""Frozen shared harness for bounded canonical summon witnesses."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.witness_canonical_roster_trio import read,sha,eq,events,finish as frozen_finish
PACKAGE=Path(os.environ.get('CAMPAIGN_SUMMON_PACKAGE',str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_roster.json')))
LAST_SIM=None


def finish(sim,roundtrip=True):
    from ark_sim.contracts import thaw
    value=frozen_finish(sim,roundtrip=roundtrip)
    kinds={'healing.accepted','healing.rejected','projectile.launched','entity.created','entity.died','entity.retired','command.accepted','movement.displaced','ability.interrupted','blocking.changed'}
    value['additional_events']=[thaw(e) for e in sim.session.events if e['type'] in kinds]
    value['entities']=[{'id':e['id'],'definition':e['definition_id'],'alive':sim.ctx.alive(e['id']),'blocked_by':sim.ctx.spatial.blocked_by(e['id']),
        'ownership':thaw(e['components'].get('ownership',{})),
        'resources':{k:v['current'] for k,v in e['components'].get('resources',{}).items()}} for e in sim.session.world.entities()]
    value['replay_inputs']=sim.export_replay()
    value['fixture_scenario_inputs']={k:thaw(sim.program.scenario[k]) for k in ('initialEntities','waves','resources','parameters','map','roster') if k in sim.program.scenario}
    value['healing_scores']=[{'time':e['time'],'source':e['payload']['source'],'target':e['payload']['target'],
        'rule_id':e['payload']['rule_id'],'score':e['payload']['value'],
        'health_ratio':e['payload']['trace']['context'].get('health_ratio')} for e in sim.session.events
        if e['type']=='calculation' and e['payload']['calculation_id']=='targeting.score' and e['payload']['trace']['context'].get('healing')]
    return value


def actor(cid,alias,row=4,col=4,sp=None,hp=None):
    item={'definition':'unit/'+cid,'instanceAlias':alias,'position':{'row':row,'col':col},'facing':'right'}
    resources={}
    if sp is not None:resources['sp']={'initial':sp}
    if hp is not None:resources['hp']={'initial':hp}
    if resources:item['components']={'resources':resources}
    return item


def scene(initial,dp=50,capacity=8,package=None):
    data=read(package or PACKAGE)
    data['scenarioDraft'].update(id='scenario/canonical_summon_witness',map={'rows':9,'cols':12},
        waves=[],scheduledEffects=[],objectives={},initialEntities=deepcopy(initial))
    data['scenarioDraft'].pop('timeline',None)
    data['scenarioDraft']['resources']['dp']['initial']=dp
    data['scenarioDraft']['parameters']['deploy_capacity']=capacity
    return data


def make(data,seed=11):
    global LAST_SIM
    from ark_sim import Compiler,Engine
    LAST_SIM=Engine.create(Compiler().compile(data),seed=seed)
    return LAST_SIM


def command(sim,source,ability,at=None,**payload):
    action={'action':'skill','source':source,'ability':ability}
    if payload:action['payload']=payload
    sim.submit(action,at=at)


def token(sim,definition,owner='host',alive=True):
    owner=sim.session.world.resolve(owner)
    matches=[e['id'] for e in sim.session.world.entities() if e['definition_id']==definition
        and e['components'].get('ownership',{}).get('owner')==owner and (not alive or sim.ctx.alive(e['id']))]
    assert len(matches)==1,matches
    return matches[0]


def run_case(name,fn):
    global LAST_SIM
    LAST_SIM=None
    try:value={'case':name,'result':'passed','actual':fn()}
    except Exception as error:
        value={'case':name,'result':'failed','error':repr(error)}
        if LAST_SIM is not None:value['actual']=finish(LAST_SIM,roundtrip=False)
        output=os.environ.get('CAMPAIGN_SUMMON_CASE_RESULTS')
        if output:
            with open(output,'a',encoding='utf8') as stream:stream.write(json.dumps(value)+'\n')
        raise
    output=os.environ.get('CAMPAIGN_SUMMON_CASE_RESULTS')
    if output:
        with open(output,'a',encoding='utf8') as stream:stream.write(json.dumps(value)+'\n')
    return value


def export(cases,test_path,tool_path,output,cids,source_paths,selected=None,package=None):
    from ark_sim.adapters.api import implementation_digest
    selected=selected or list(cases)
    package=Path(package or PACKAGE)
    files=[package,test_path,tool_path,Path(__file__),ROOT/'tools/witness_canonical_roster_trio.py',*source_paths]
    before={'implementation_sha256':implementation_digest(),'files':{str(p.resolve()):sha(p) for p in files}}
    with tempfile.TemporaryDirectory(prefix='ark_owned_') as directory:
        path=Path(directory)/'cases.jsonl'
        env=dict(os.environ,CAMPAIGN_SUMMON_CASE_RESULTS=str(path),CAMPAIGN_SUMMON_PACKAGE=str(package.resolve()))
        nodes=[str(test_path)+'::test_canonical_mechanism['+name+']' for name in selected]
        process=subprocess.run([sys.executable,'-m','pytest',*nodes,'-q','--tb=short'],cwd=ROOT,env=env,capture_output=True,text=True)
        results=[json.loads(line) for line in path.read_text(encoding='utf8').splitlines()] if path.exists() else []
    after={'implementation_sha256':implementation_digest(),'files':{str(p.resolve()):sha(p) for p in files}}
    stable=before==after
    passed=stable and process.returncode==0 and len(results)==len(selected) and all(c['result']=='passed' for c in results)
    normalized=read(ROOT/'packages/campaign/operators.normalized.json')
    result={'schema':'ark-sim/campaign-mechanism-test-evidence/v1','passed':passed,
        'implementation_sha256':before['implementation_sha256'],'identity_stable':stable,
        'identity_at_start':before,'identity_at_completion':after,'input_package':str(package.resolve()),'input_package_sha256':sha(package),
        'tests':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(p),'result':'passed' if passed else 'failed'} for p in files[1:5]],
        'source_hashes':{str(p):sha(p) for p in source_paths},
        'configs':{r['character_id']:r['config'] for r in normalized['operators'] if r['character_id'] in cids},
        'selected_cases':selected,'cases':results,'pytest_output':process.stdout+process.stderr,'pytest_exit_code':process.returncode,
        'scope':'bounded canonical mechanism witnesses only','review_receipt':False,'formal_approval':False,'client_pending_preserved':True}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':passed,'identity_stable':stable,'failed':[c['case'] for c in results if c['result']!='passed'],'output':str(output)}))
    return 0 if passed else 1
