"""Final source start invokes declared Hint callback and cancels source hints."""
import json
from copy import deepcopy
from pathlib import Path
from tools.chapter08_joint_v4.build_bsnake_four_modes_v1 import OUT as PARENT, SOURCE, sha

OUT = PARENT.with_name('four_modes.module.v2.json')
HINT = 'ability/ch8/bsnake/hint'


def build():
    p = json.loads(PARENT.read_bytes())
    definitions = {row['id']: row for row in p['definitions']}
    entity = definitions['unit/ch8/bsnake/cadb87696bef4de2']
    terminal = entity['components']['rebirth']['zero_restore_lifecycle']
    terminal['owned_abilities'].append(HINT)
    hint = definitions[HINT]
    hint['activation'].pop('condition')
    for effect in hint['activation']['on_start']:
        if effect.get('event') == 'source.bsnake.hint.show':
            effect['condition'] += ' and inputs.source.components.resources.mode.current < 3'
    terminal['on_enter'].append({'op': 'trigger_ability', 'target': 'source', 'ability': HINT})
    p['manifest']['id'] = 'package/ch8/bsnake/four_modes_v2'
    meta = p['manifest']['metadata']
    meta['source_locks'].update({str(path.resolve()): sha(path) for path in (PARENT, Path(__file__))})
    meta['join_overrides'].append('FinalONSTART ownHint explicit callback executesclear while mode3 cancellation hides show keys')
    return p


if __name__ == '__main__':
    assert not OUT.exists()
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(sha(OUT))
