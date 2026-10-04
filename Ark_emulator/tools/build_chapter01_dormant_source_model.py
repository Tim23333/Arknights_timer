"""Bind the source-isolation revision without rewriting the db6134 wrapper."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_chapter01_dormant_model import build as parent_build
from tools.build_chapter01_stage_models import encoded, sha

PARENT = ROOT/'packages/campaign/chapter01_stage_models/m20/level_main_01-11.dormant.partial.json'
PIN = '335ca3e10fec3e85396ec39d1e2fc82a598268d28c45a7cd2ec14343067ad7c6'
RUNTIME = ROOT.parent/'unpack_work/campaign_m20_dormant_source_candidate'
CORE = 'b506ee18e7137c3658f1fe8ce77b4b612bf48bceb9b02446f2dfcb7d91abbf0d'
OUT = ROOT/'packages/campaign/chapter01_stage_models/m20_source/level_main_01-11.dormant.partial.json'


def build():
    if sha(PARENT) != PIN: raise ValueError('frozen dormant input drift')
    p = json.loads(PARENT.read_bytes())
    if p != parent_build(): raise ValueError('frozen dormant builder drift')
    meta = p['manifest']['metadata']
    meta.update(required_runtime=CORE, builder_sha256=sha(Path(__file__)), parent_dormant_sha256=PIN)
    meta['source_locks'][PARENT.relative_to(ROOT).as_posix()] = PIN
    p['manifest']['id'] += '/source_isolation'
    p['scenarioDraft']['id'] += '/source_isolation'
    return p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    sys.path.insert(0, str(RUNTIME))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent != RUNTIME/'ark_sim' or implementation_digest() != CORE:
        raise RuntimeError('wrong dormant source candidate')
    p = build(); program = Compiler().compile(p); OUT.parent.mkdir(parents=True, exist_ok=True)
    if args.check:
        if OUT.read_bytes() != encoded(p): raise ValueError('source model drift')
    else: OUT.write_bytes(encoded(p))
    print(json.dumps({'implementation': CORE, 'definitions': len(program.definitions), 'package_sha256': sha(OUT), 'whole_stage': False}))
