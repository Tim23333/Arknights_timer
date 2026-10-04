"""Bind current consumed NPC inputs and proofs with explicit older-version scope."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    base=ROOT/'validation/campaign/chapter06_npcs_author_v1/freeze.json'
    old=json.loads(base.read_bytes());current={p:sha(Path(p)) for p in old['files']}
    changed={p:{'old_sha':pin,'current_sha':current[p]} for p,pin in old['files'].items() if current[p]!=pin}
    packages=['inputs.reference.json','swllow.v2.model.json','amiya.v3.model.json',
        'story_controls.v2.model.json','huang_talents.v7.model.json','huang.v7.model.json']
    paths=[ROOT/'packages/campaign/chapter06_npcs'/name for name in packages]
    paths += list((ROOT/'tools/chapter06_npcs').glob('*.py'))
    paths += [ROOT/'packages/campaign/chapter06_predefines/source.reference.json',
              ROOT/'validation/campaign/chapter06_npc_huang_v7_guarded/verification.json',
              ROOT/'validation/campaign/chapter06_npc_huang_v7_sameframe/verification.json',
              ROOT/'validation/campaign/chapter06_npc_independent_peer_v2_frozen/verification.json',
              base,Path(__file__)]
    files={str(p):sha(p) for p in paths}
    target=ROOT/'validation/campaign/chapter06_npcs_author_v2/freeze.json';target.parent.mkdir(exist_ok=False)
    report={'schema':'ark-sim/source-content-author-freeze/v1','files':files,
        'historical_freeze_sha':sha(base),'historical_paths_changed_since_freeze':changed,
        'current_runtime_candidate':'1cb64a004d15f0b365c0affc02ad900444cd9e5ca263707f7c176c3f3bd1c4fd',
        'scope':'Current NPC content author snapshot. Historical proofs keep their original provider/source identities. New Huang provider and guarded proofs bound separately; independent expanded review pending.',
        'whole_stage_executed':False,'client_verified':False,'formal_approval':False}
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'files':len(files),'changed_old_paths':len(changed),'sha':sha(target)}))


if __name__=='__main__':main()
