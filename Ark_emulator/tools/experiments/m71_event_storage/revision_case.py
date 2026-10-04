"""Actual v12 checkpoint-file reload order regression, preserving frozen M71."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent/'unpack_work/campaign_m71_event_storage_candidate'
OUT = ROOT/'validation/campaign/m71_event_storage/final_revision'
sys.path.insert(0, str(RUNTIME))
sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.contracts.models import thaw
from ark_sim.tools.compare import first_difference


def helper(filename):
    path = ROOT/'tools/candidates/m71_event_storage'/filename
    spec = importlib.util.spec_from_file_location(filename.replace('.', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checkpoint_values(sim):
    cp = sim.checkpoint()
    return {'world': cp['kernel']['world'], 'scheduler': cp['kernel']['scheduler'],
            'random': cp['kernel']['random'], 'events': cp['kernel']['events'],
            'snapshot': sim.snapshot()}


def case(module, run, label):
    source = ROOT/'packages/custom/custom_guard.json'
    package = json.loads(source.read_text(encoding='utf8'))
    # Existing real Compiler/Engine/ResourceSystem drives both resources.
    package['scenarioDraft']['initialEntities'] = []
    package['scenarioDraft']['commands'] = []
    package['scenarioDraft']['resources'] = {
        'zeta': {'initial': 0, 'capacity': 1000, 'recovery_rate': 1},
        'alpha': {'initial': 0, 'capacity': 1000, 'recovery_rate': 2}}
    (run/(label+'-controlled-package.json')).write_text(json.dumps(package, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    program = Compiler().compile(package)
    original = Engine.create(program, seed=123, event_journal_path=run/(label+'-active.jsonl'))
    original.session.advance(3)
    original.session.random.sample('combat')
    path = run/(label+'-checkpoint.json')
    meta = module.write_checkpoint(original, path)
    loaded_checkpoint = module.load_checkpoint(meta) if hasattr(module, 'load_checkpoint') else json.loads(path.read_bytes())
    restored = Engine.restore(program, loaded_checkpoint)
    before = checkpoint_values(original)
    loaded = checkpoint_values(restored)
    original.session.advance(60)
    restored.session.advance(60)
    expected = checkpoint_values(original)
    actual = checkpoint_values(restored)
    for name, value in [('before', before), ('loaded', loaded), ('expected', expected), ('actual', actual)]:
        (run/(label+'-'+name+'-full-values.json')).write_text(json.dumps(value, ensure_ascii=False), encoding='utf8')
    first = first_difference(expected, actual)
    order_before = list(before['world']['entities'][0]['components']['resources'])
    order_loaded = list(loaded['world']['entities'][0]['components']['resources'])
    return {'label': label, 'metadata': meta, 'first_difference': first,
            'resource_key_order_before': order_before, 'resource_key_order_after_reload': order_loaded,
            'full_continuation_equal': first is None, 'time': original.session.time,
            'counts': [len(expected['events']['records']), len(actual['events']['records'])],
            'section_equal': {key: first_difference(expected[key], actual[key]) is None for key in expected},
            'program_fingerprint': program.fingerprint, 'runtime_fingerprint': original.runtime_fingerprint}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    run = OUT/('reproduction-'+uuid.uuid4().hex)
    run.mkdir()
    result = case(helper('campaign_streaming_evidence_v12.py'), run, 'v12')
    report = {'schema': 'ark-sim/m71-checkpoint-order-reproduction/v1',
              'actual_file_reload': True, 'run': str(run), 'case': result,
              'v12_sha256': sha(ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v12.py'),
              'script_sha256': sha(Path(__file__))}
    target = OUT/'v12-reproduction.json'
    with target.open('x', encoding='utf8') as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write('\n')
    print(json.dumps(report, ensure_ascii=False))

if __name__ == '__main__':
    main()
