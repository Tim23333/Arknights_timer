"""Assemble a new receipt from immutable forward/CP and actual replay evidence."""
import argparse,hashlib,json
from copy import deepcopy
from pathlib import Path
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--proof',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    proof=json.loads(args.proof.read_bytes())
    assert proof['schema']=='ark-sim/persisted-original-replay-proof/v17'
    assert proof['passed'] is True and proof['replay_equal'] is True and proof['actual_helper_exit']==0
    assert proof['identity_stable'] is True and proof['core_start']==proof['core_end']
    assert proof['source_at_start']==proof['source_at_completion'] and proof['helper_guards_start']==proof['helper_guards_completion']
    assert proof['original_observations']==proof['replay_observations']
    original_path=Path(proof['forward_process_reused']['path']);prior_path=Path(proof['checkpoint_proof_reused']['path'])
    assert sha(original_path)==proof['forward_process_reused']['sha256']==proof['original_sha256']
    assert sha(prior_path)==proof['checkpoint_proof_reused']['sha256']
    original=json.loads(original_path.read_bytes());prior=json.loads(prior_path.read_bytes())
    assert original['process_complete'] is True and prior['checkpoint_equal'] is True and prior['durable_checkpoint_equal'] is True
    assert original['implementation']==prior['implementation']==proof['core_end']
    assert original['program']==prior['program'] and original['package_sha256']==prior['package_sha256'] and original['commands_sha256']==prior['commands_sha256']
    assert original['observations']==proof['original_observations'] and original['checkpoint_sha256']==proof['checkpoint_proof_reused']['checkpoint_sha256']
    assert original['source_at_start']==prior['source_at_start']==prior['source_at_completion']==proof['source_at_start']==proof['source_at_completion']
    checkpoint=Path(prior['checkpoint']);assert sha(checkpoint)==prior['checkpoint_sha256']
    output=deepcopy(original)
    for key in ('checkpoint','checkpoint_sha256','checkpoint_encoding','checkpoint_equal','durable_checkpoint_equal','checkpoint_error'):
        output[key]=deepcopy(prior[key])
    output.update(passed=True,replay_equal=True,replay_error=None,identity_stable=True,
        source_at_completion=proof['source_at_completion'],core_at_completion=proof['core_end'],
        proof_composition={'schema':'ark-sim/runthrough-proof-composition/v1',
            'forward':{'path':str(original_path),'sha256':sha(original_path)},
            'checkpoint':{'path':str(prior_path),'sha256':sha(prior_path)},
            'replay':{'path':str(args.proof.resolve()),'sha256':sha(args.proof)},
            'actual_replay_observations':proof['replay_observations'],'same_core_content_commands':True},
        actual_game_accuracy_verified=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf8') as f:json.dump(output,f,ensure_ascii=False,sort_keys=True,separators=(',',':'));f.write('\n')
    print(json.dumps({'output':str(args.output),'sha256':sha(args.output),'passed':True}))
if __name__=='__main__':main()
