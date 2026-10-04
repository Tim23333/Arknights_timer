"""Only 99999 base life on an exact reconstructed native source draft."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.append(str(ROOT))
from tools.chapter06_review.stage_converter_v7 import exact


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def apply(parent,parent_sha,commands_sha):
    from tools.chapter07_join.build_stage_draft_v2 import build
    expected=build()
    if not exact(expected,parent):raise ValueError('Native parent differs from source reconstruction')
    p=deepcopy(parent);scene=p['scenarioDraft'];native=deepcopy(scene['resources']['life'])
    scene['resources']['life']={'initial':99999,'capacity':99999}
    scene['metadata']['runthrough_profile']={
        'base_life_resource':'life','base_life':99999,'fixed12':deepcopy(scene['roster']),
        'source_births':37,'deploy_capacity':9,'public_commands_sha256':commands_sha,
        'operator_enemy_HP':'Original exact source module HP','training_deployment_exception':False,
        'client_verified':False,'accuracy':'Reference-source model; user client feedback pending'}
    p['manifest']['metadata']['goal_base_life_authoring']={
        'native':native,'selected_initial':99999,'selected_capacity':99999,'only_authoring':'Campaign user base life policy'}
    # Parent SHA is retained by the external input receipt; only the standard
    # life profile/provenance fields are added to the battle package.
    restored=deepcopy(p);restored['scenarioDraft']['resources']['life']=native
    del restored['scenarioDraft']['metadata']['runthrough_profile']
    del restored['manifest']['metadata']['goal_base_life_authoring']
    if not exact(restored,parent):raise ValueError('Life overlay changed another native input')
    return p


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True)
    ap.add_argument('--parent',type=Path,required=True);ap.add_argument('--commands',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    value=apply(json.loads(args.parent.read_bytes()),sha(args.parent),sha(args.commands))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'parent_sha':sha(args.parent),'overlay_sha':sha(args.output),'base_life':99999,'other_battle_inputs_exact':True}))


if __name__=='__main__':main()
