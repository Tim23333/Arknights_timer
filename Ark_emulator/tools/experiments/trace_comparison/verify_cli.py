"""Exercise comparator CLI on real V2 observations and synthetic expectations."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from tools.experiments.m26.test_decisions import fixture, make
from ark_sim.adapters.api import implementation_digest


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = ROOT/'validation/campaign/trace_comparison';out.mkdir(parents=True,exist_ok=True)
    core = implementation_digest(); sim = make(fixture())
    identity = {'stage_id':'synthetic/enemy_decision','game_build':'synthetic_fixture_no_client',
        'platform':'synthetic','content_identity':sim.program.fingerprint,'roster_identity':'fixture/one_enemy_one_target',
        'commands_identity':'empty','episode_identity':'synthetic/decision_attack'}
    model = {'schema':'ark-sim/intermediate-trace/v1','origin':'ark_sim','identity':identity,'samples':[]}
    expected = {'schema':'ark-sim/intermediate-trace/v1','origin':'synthetic_test','identity':identity,'samples':[]}
    for tick,hp in [(0,100),(6,100),(7,80),(8,80)]:
        sim.advance(tick-sim.session.time)
        values = {'target/hp':sim.ctx.resources.current('target','hp'),'enemy/col':sim.ctx.get('enemy',('spatial','position'))['col']}
        model['samples'].append({'frame':tick,'frame_before':tick,'frame_after':tick,'complete':True,'values':values})
        expected['samples'].append({'frame':tick,'frame_before':tick,'frame_after':tick,'complete':True,'values':{'target/hp':hp,'enemy/col':0}})
    contract = {'schema':'ark-sim/intermediate-comparison-contract/v1','identity':identity,'native_frames':[0,6,7,8],
        'time_mapping':{'native_origin':0,'model_origin':0,'numerator':1,'denominator':1,'evidence':'same synthetic model quantum'},
        'fields':[{'name':'target_hp','native_key':'target/hp','model_key':'target/hp','mode':'exact'},
                  {'name':'enemy_col','native_key':'enemy/col','model_key':'enemy/col','mode':'absolute_tolerance',
                   'semantic_type':'continuous_coordinate','tolerance':0,'evidence':'synthetic stationary zero coordinate'}],
        'uncovered_requirements':['actual client capture','native frame mapping','whole-stage field coverage']}
    for name,value in [('model.json',model),('synthetic_expected.json',expected),('contract.json',contract)]:save(out/name,value)
    arguments = [sys.executable,str(ROOT/'tools/compare_campaign_trace.py'),'--native',str(out/'synthetic_expected.json'),
        '--model',str(out/'model.json'),'--contract',str(out/'contract.json'),'--output',str(out/'matched.json')]
    matched = subprocess.run(arguments,cwd=ROOT,capture_output=True,text=True)
    # Preserve an intermediate HP discrepancy, while the final HP stays80.
    mismatched_model = copy.deepcopy(model);mismatched_model['samples'][2]['values']['target/hp']=81;save(out/'model_mismatch.json',mismatched_model)
    arguments[arguments.index('--model')+1] = str(out/'model_mismatch.json'); arguments[-1] = str(out/'mismatched.json')
    failed = subprocess.run(arguments,cwd=ROOT,capture_output=True,text=True)
    a,b = json.loads((out/'matched.json').read_bytes()),json.loads((out/'mismatched.json').read_bytes())
    passed = (matched.returncode==0 and failed.returncode==1 and a['comparison_passed'] and not b['comparison_passed']
              and b['first_difference']['native_frame']==7 and not a['actual_game_accuracy_verified']
              and core==implementation_digest())
    report = {'schema':'ark-sim/offline-trace-comparator-cli-check/v1','passed':passed,'core':core,'core_end':implementation_digest(),
        'runtime':str(RUNTIME),'native_origin':'synthetic_test','actual_game_accuracy_verified':False,
        'matched_exit_code':matched.returncode,'mismatched_exit_code':failed.returncode,
        'matched_output':matched.stdout+matched.stderr,'mismatched_output':failed.stdout+failed.stderr,
        'first_difference':b['first_difference'],'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in
            [Path(__file__),ROOT/'tools/compare_campaign_trace.py',out/'model.json',out/'synthetic_expected.json',out/'contract.json',out/'matched.json',out/'mismatched.json']}}
    save(out/'cli_verification.json',report); print(json.dumps({'passed':passed,'matched':matched.returncode,'mismatched':failed.returncode}))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':main()
