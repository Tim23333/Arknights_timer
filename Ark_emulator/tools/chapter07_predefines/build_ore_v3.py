"""Complete the temporary content payload marker after each source operation."""
import json
from pathlib import Path
from tools.chapter07_predefines.build_ore_v1 import ROOT, STEM, sha


def main():
    folder = ROOT / 'packages/campaign/chapter07_predefines_consumer'
    p = json.loads((folder / 'ore.module.v2.json').read_bytes())
    p['manifest']['id'] = 'package/' + STEM + '/v3'
    p['manifest']['metadata']['source_locks'][str(Path(__file__).resolve())] = sha(Path(__file__))
    for buff in p['buffs']:
        if not buff['id'].endswith('_payload'):
            continue
        if buff['id'].endswith('/damage_payload'):
            buff['effects'][0]['parameters'] = {'consider_unhurtable': False}
        buff['effects'].append({'op': 'remove_buff', 'buff': buff['id']})
    p['manifest']['metadata']['reference_policy'] += (
        ' Temporary content payload markers self-remove synchronously after the operation. '
        'consider_unhurtable=false is provided to explicit source invulnerability hook conditions, '
        'and other damage modifier events remain enabled.')
    out = folder / 'ore.module.v3.json'
    assert not out.exists()
    out.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='')
    print(json.dumps({'sha256': sha(out)}))


if __name__ == '__main__':
    main()
