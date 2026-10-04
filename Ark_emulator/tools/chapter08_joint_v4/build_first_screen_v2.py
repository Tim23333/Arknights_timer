"""Preserve source BuffDuringCasting flags22/5 without misnaming22 as invisible."""
import json
from pathlib import Path
from tools.chapter08_joint_v4.build_first_screen_v1 import OUT as PARENT, SOURCE, SCREEN, sha

OUT = PARENT.with_name('first_screen.module.v2.json')


def build():
    source = json.loads(SOURCE.read_bytes())
    native = source['prefab']['components']['-4235527712895175292']
    assert native['native_class'] == 'BuffDuringCasting'
    assert native['raw']['_buffs'][0]['attributes']['abnormalFlags'] == [22, 5]
    p = json.loads(PARENT.read_bytes())
    next(row for row in p['buffs'] if row['id'] == SCREEN)['selection_flags']['abnormal_flags'] = [22, 5]
    p['manifest']['id'] = 'package/ch8/bsnake/first_screen_v2'
    meta = p['manifest']['metadata']
    meta['source_locks'].update({str(path.resolve()): sha(path) for path in (PARENT, Path(__file__))})
    meta['source_buff_during_casting'] = native
    meta['enum_mapping'] = {'UNMOVABLE_PRIVATE': 22, 'INVINCIBLE': 5, 'INVISIBLE': 9}
    meta['reference_policy'] = ('Originalthree-row controlledray geometry. Sourcecasting flags22UNMOVABLE_PRIVATE/5INVINCIBLE preserved; '
                                'INVINCIBLE maps target_free for normal selection plus damage rejection. Casting28 duration projected finiteBuff, '
                                'sourcefirstscreen28/endmode1/invincible15 realconsumer; separate ordinaryskill gating and fullcasting-node ownership pending join.')
    return p


if __name__ == '__main__':
    assert not OUT.exists()
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(sha(OUT))
