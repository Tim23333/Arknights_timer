"""Only base-life/profile/provenance overlay; all native simulation inputs kept."""
from copy import deepcopy
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.append(str(ROOT))
from tools.chapter06_review.stage_converter_v7 import exact


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def apply(parent,commands_sha):
    from tools.chapter06_review.validate_stage_parent_v1 import validate
    validate(parent)
    p=deepcopy(parent);s=p['scenarioDraft'];native=deepcopy(s['resources']['life'])
    if len(s['roster'])!=12:raise ValueError('Fixed12 roster required')
    count=sum(a.get('count',1) for w in s['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn')
    s['resources']['life'].update(initial=99999,capacity=99999)
    s['metadata']['runthrough_profile']={'base_life_resource':'life','base_life':99999,'fixed12':deepcopy(s['roster']),
        'operator_enemy_HP':'Original exact source module HP','source_births':count,'deploy_capacity':s['parameters']['deploy_capacity'],
        'public_commands_sha256':commands_sha,'training_deployment_exception':p['manifest']['metadata']['training_deployment_exception'],
        'client_verified':False,'accuracy':'Source-reference model and explicit policies; user client feedback pending'}
    p['manifest']['metadata']['goal_base_life_authoring']={'native':native,'selected_initial':99999,'selected_capacity':99999,'only_authoring':'Campaign user base life policy'}
    restore=deepcopy(p);restore['scenarioDraft']['resources']['life']=native
    del restore['scenarioDraft']['metadata']['runthrough_profile'];del restore['manifest']['metadata']['goal_base_life_authoring']
    if not exact(restore,parent):raise ValueError('Base-life overlay changed other source inputs')
    return p


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--parent',type=Path,required=True);ap.add_argument('--commands',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True)
    a=ap.parse_args();sys.path.insert(0,str(a.runtime_root.resolve()))
    from ark_sim.adapters.api import implementation_digest
    if implementation_digest()!=a.expected_core:raise ValueError('Source overlay runtime identity differs')
    p=apply(json.loads(a.parent.read_bytes()),sha(a.commands));a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf8') as f:json.dump(p,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'parent_sha':sha(a.parent),'overlay_sha':sha(a.output),'base_life':99999,'other_source_inputs_exact':True}))


if __name__=='__main__':main()
