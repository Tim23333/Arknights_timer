"""Derive source crate with explicit selected-route contact eligibility."""
import argparse,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'packages/campaign/chapter03_traps/crate.partial.reference_model.json'
PIN='167e67077038e24bd17d03552016710b3c8785a5005bd9e5ec0051d54393695a'
OUT=ROOT/'packages/campaign/chapter03_traps/crate.obstacle.reference_model.json'


def build():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PIN:raise ValueError('Frozen crate source partial drift')
    p=json.loads(PARENT.read_bytes());unit=p['entities'][0]
    source=ROOT/'packages/campaign/chapter03_plans/source.plan.json'
    if hashlib.sha256(source.read_bytes()).hexdigest()!='d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6':raise ValueError('Frozen obstacle radius source drift')
    plan=json.loads(source.read_bytes());root=next(r['raw'] for r in plan['selected_native_prefabs']['trap_001_crate']['components'].values() if r['native_class']=='MapDependentTrap')
    unit['components']['route_obstacle']={'rule':'rule/ch3/crate_obstacle_contact','contact_radius':math.sqrt(root['_blockRadiusSquare']),
        'parameters':{'allowed_source_side':1,'obstacle_side':0}}
    p['rules']=[{'id':'rule/ch3/crate_obstacle_contact','kind':'rule','contract':'blocking.obstacle','implementation':{'type':'expression',
        'expression':'inputs.source.components.selection_state.side == inputs.parameters.allowed_source_side and inputs.obstacle.components.selection_state.side == inputs.parameters.obstacle_side'}}]
    p['manifest']['id']+='/selected_route_obstacle';p['manifest']['metadata'].update(parent_partial_sha256=PIN,
        obstacle_builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),required_core_contract='blocking.obstacle',
        model_gaps=['Enemy source combat selector must permit sourceOBSTACLE4 or explicit obstacle-only fallback ability/profile; independentstageclosure pending'],
        contact_policy={'radius':'sqrt(native _blockRadiusSquare .20000000298)','selected_path':'only actual remaining chosen weighted route cell contact','blocking_capacity':'independent from ordinary character blockCnt3; all movers can contact'},
        native_runtime_ready=False)
    unit['metadata']['declared_model_blocking']='Explicit selected-route obstacle contact, ordinary characterblock0; sourcecategory4 kept'
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Crate obstacle input changed')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'category_source':4,'ordinary_block_count':0}))
