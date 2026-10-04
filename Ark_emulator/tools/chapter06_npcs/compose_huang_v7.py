"""Join source attack and repaired passive content without changing old models."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    folder=ROOT/'packages/campaign/chapter06_npcs'
    base=folder/'huang.model.json';talent=folder/'huang_talents.v7.model.json'
    p=json.loads(base.read_bytes());new=json.loads(talent.read_bytes())
    for key in ('rules','buffs','selectors'):
        replacements={d['id']:d for d in new.get(key,[])}
        p[key]=[d for d in p.get(key,[]) if d['id'] not in replacements]+list(replacements.values())
    p['manifest']['metadata'].update(passive_parent_sha=hashlib.sha256(talent.read_bytes()).hexdigest(),
        attack_parent_sha=hashlib.sha256(base.read_bytes()).hexdigest(),
        builder_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        passive_provider='tools.chapter06_npcs.huang_v6_policy.providers',
        source_qualification='Effective maxHP quarter threshold, dynamic HealFree, one reaction per parent; explicit deferred callback policy')
    path=folder/'huang.v7.model.json';assert not path.exists()
    path.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
