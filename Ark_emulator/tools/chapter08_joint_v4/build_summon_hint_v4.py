"""Hint callbacks do not block their invoking cast; stable resolved builder identity."""
import json
from pathlib import Path
from tools.chapter08_joint_v4.build_summon_hint_v3 import OUT as PARENT
from tools.chapter08_joint_v4.build_summon_hint_v2 import sha, SUMMON
from tools.chapter08_joint_v4.build_summon_hint_v1 import HINT, COUNTDOWN

OUT = PARENT.with_name('summon_hint.module.v4.json')


def build():
    p = json.loads(PARENT.read_bytes())
    p['manifest']['id'] = 'package/ch8/bsnake/summon_hint_v4'
    p['manifest']['metadata']['source_locks'].update({str(path.resolve()): sha(path) for path in (PARENT, Path(__file__))})
    for row in p['abilities']:
        if row['id'] in (HINT, COUNTDOWN):
            row['activation']['parameters']['blocks_attacks'] = False
    return p


if __name__ == '__main__':
    assert not OUT.exists()
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(sha(OUT))
