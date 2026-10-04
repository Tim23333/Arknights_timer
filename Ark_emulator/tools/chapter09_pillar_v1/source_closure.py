"""Offline recursive pillar BSON closure; never delegates combat to V1."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.chapter07.native_assets_v1 import bson_source, find_templates


def main():
    source = ROOT / 'packages/campaign/chapter09_source_prepare/predefines.native.v3.json'
    data = json.loads(source.read_bytes())
    keys = find_templates(data['prefabs']['trap_043_dupilr']) | find_templates(data['skill_prefabs']['sktok_dupilr'])
    seen = set()
    for _ in range(32):
        seen |= keys
        closure = bson_source(seen)
        keys = find_templates(closure['templates']) - seen
        if not keys:
            break
    else:
        raise ValueError('Native template closure exceeds finite bound')
    result = {'schema': 'ark-sim/ch9-pillar-transitive-bson/v1', 'offline_only': True,
              'source_predefines_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'required_keys': sorted(seen), 'closure': closure,
              'builder_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'whole_stage_verified': False}
    output = ROOT / 'packages/campaign/chapter09_consumers/pillars/source.closure.v1.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'keys': len(seen), 'missing': closure['missing_templates'],
                      'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
