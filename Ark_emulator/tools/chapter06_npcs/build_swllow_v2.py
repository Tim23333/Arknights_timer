"""Actual air-capable source selector; target-free/camo eligibility retained."""
import hashlib,json
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'packages/campaign/chapter06_npcs/swllow.model.json'
SOURCE=ROOT/'packages/campaign/chapter06_predefines/source.reference.json'


def main():
    from ark_sim.domains.selection import DEFAULT_STATE
    parent=json.loads(BASE.read_bytes());source=json.loads(SOURCE.read_bytes());prefab=source['prefabs']['char_367_swllow']
    cfg=deepcopy(prefab['components']['-4661434853902386322']['raw'])
    assert cfg['_targetMotion']==3 and cfg['_targetSide']==2 and cfg['_targetCategory']==1
    defaults=deepcopy(DEFAULT_STATE);defaults.update(side=0,motion=1,category=1,unit_type=1)
    unit=parent['entities'][0];unit['components']['selection_state']=deepcopy(defaults)
    rule='rule/ch6/npc/swllow_eligible'
    parent['rules'].append({'id':rule,'kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}})
    selector=parent['selectors'][0];selector['filters']=[x for x in selector['filters'] if x!={'tag':'ground'}]
    selector['eligibility']={'rule':rule,'parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}}
    parent['manifest']['metadata'].update(parent_sha=hashlib.sha256(BASE.read_bytes()).hexdigest(),source_selector=cfg,
        selector_policy='NativeSecondaryFilter0/motion3/side2/category1 and target-free/camo gates; original range offsets and one target retained')
    path=BASE.with_name('swllow.v2.model.json');assert not path.exists();path.write_text(json.dumps(parent,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
