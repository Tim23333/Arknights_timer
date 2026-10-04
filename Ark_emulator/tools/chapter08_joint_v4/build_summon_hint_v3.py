"""Enable declared automatic source skill while preserving callback-only hint APIs."""
import json
from pathlib import Path
from tools.chapter08_joint_v4.build_summon_hint_v2 import OUT as PARENT, sha, SUMMON

OUT = PARENT.with_name('summon_hint.module.v3.json')


def build():
    p = json.loads(PARENT.read_bytes())
    p['manifest']['id'] = 'package/ch8/bsnake/summon_hint_v3'
    p['manifest']['metadata']['source_locks'].update({str(path): sha(path) for path in (PARENT, Path(__file__))})
    next(row for row in p['abilities'] if row['id'] == SUMMON)['activation']['parameters']['auto_when_ready'] = True
    p['manifest']['metadata']['reference_policy'] += ' Automatic readiness consumes declared mode1/branchavailability; cooldown counts castend+50 per generic current source timing. Source _timeMode0/ASPD Skill3 timing requires final timing integration.'
    return p


if __name__ == '__main__':
    assert not OUT.exists()
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(sha(OUT))
