"""Bind nested qualified-area and application rule dependencies explicitly."""
import json
from pathlib import Path
from tools.chapter07_predefines.build_ore_v1 import ROOT, STEM, sha


def main():
    p = json.loads((ROOT / 'packages/campaign/chapter07_predefines_consumer/ore.module.v1.json').read_bytes())
    area = next(r for r in p['rules'] if r['id'].endswith('/area'))
    area['dependencies'] = ['rule/' + STEM + '/eligibility']
    p['manifest']['id'] = 'package/' + STEM + '/v2'
    p['manifest']['metadata']['source_locks'][str(Path(__file__).resolve())] = sha(Path(__file__))
    out = ROOT / 'packages/campaign/chapter07_predefines_consumer/ore.module.v2.json'
    assert not out.exists()
    out.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='')
    print(json.dumps({'sha256': sha(out)}))


if __name__ == '__main__':
    main()
