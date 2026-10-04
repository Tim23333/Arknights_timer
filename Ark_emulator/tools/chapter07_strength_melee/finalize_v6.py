"""Variant-bound derived definitions retain literal native Buff names/blackboards."""
import hashlib
import json
from pathlib import Path
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[2]
MARKER='buff/ch7/source/enemy_9D0_talent_strength'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def build(parent):
    p=json.loads(parent.read_bytes());before=deepcopy(p)
    unit=p['entities'][0];vid=unit['metadata']['native_variant']
    stat='move_speed' if 'sotisc' in vid else 'atk'
    old='buff/ch7/source/enemy_talent_strength['+stat+']'
    new='buff/'+unit['id']+'/source/enemy_talent_strength['+stat+']'
    found=[b for b in p['buffs'] if b['id']==old];assert len(found)==1
    marker=next(b for b in p['buffs'] if b['id']==MARKER)
    def rewrite(value):
        if isinstance(value,dict):
            return {k:(deepcopy(v) if k=='metadata' else rewrite(v)) for k,v in value.items()}
        if isinstance(value,list):return [rewrite(v) for v in value]
        return new if value==old else value
    p=rewrite(p)
    derived=next(b for b in p['buffs'] if b['id']==new)
    derived['metadata'].update(native_buff_key='enemy_talent_strength['+stat+']',
        source_variant=vid,definition_identity='Bound to exact consuming source variant and its blackboard; native Buff key unchanged')
    assert next(b for b in p['buffs'] if b['id']==MARKER)==marker
    assert derived['modifiers']==found[0]['modifiers']
    assert p['entities']==before['entities']
    p['manifest']['id']=p['manifest']['id'].replace('/v5','/v6')
    p['manifest']['metadata'].update(derived_definition_binding={'native_buff_key':derived['metadata']['native_buff_key'],
        'source_variant':vid,'old_local_id':old,'bound_local_id':new},
        required_runtime='4f16ac4c8ec0c0080302dfa1b6b1b6cc4da90d383ae9a2da5f796551d630c346')
    p['manifest']['metadata']['source_locks'].update({str(parent.resolve()):sha(parent),str(Path(__file__).resolve()):sha(Path(__file__))})
    return p


def main():
    folder=ROOT/'packages/campaign/chapter07_strength_melee';rows=[]
    for parent in sorted(folder.glob('*.v5.json')):
        p=build(parent);out=parent.with_name(parent.name.replace('.v5.json','.v6.json'))
        assert not out.exists();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
        rows.append({'path':str(out),'sha':sha(out)})
    print(json.dumps(rows))


if __name__=='__main__':main()
