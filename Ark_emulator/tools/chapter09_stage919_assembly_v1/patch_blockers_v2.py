"""Keep ordinary range masks; only actual blocked input permits obstacle combat."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    parent=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v1.life99999.json';p=json.loads(parent.read_bytes());changed=[]
    for name in ('dugago','durokt'):
        rule=next(d for d in p['definitions'] if d['id']=='rule/ch9/'+name+'/blocker');original=deepcopy(rule)
        assert rule['implementation']['provider']=='reference.ch9.actual_blocker'
        rule['implementation']['provider']='reference.ch9.finale_blocker'
        changed.append({'before':original,'after':deepcopy(rule)})
    p['manifest']['metadata']['actual_obstacle_input_reference']={'parent_sha':hashlib.sha256(parent.read_bytes()).hexdigest(),'changed':changed,'native_INPUT_TARGET_enum':2,'native_wrapper_body_verified':False,'source_reference':'PRTS battlefield ruins blocked-enemy destruction, as chapter9 previous source integration','whole_stage':False}
    out=parent.with_name('level_main_09-17.native_draft.v2.life99999.json');assert not out.exists();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
