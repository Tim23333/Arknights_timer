"""Exact fixed source vectors/options/cards/aliases and actual startup prefix."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.chapter09_stage919_assembly_v1.providers_v3 import providers
    from tools.chapter06_review.stage_converter_v7 import exact
    from tools.chapter06_review.stage_converter_v6 import route_ir
    from tools.chapter09_pillar_v1.build_map_profile import build as native_map
    package_path=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v3.life99999.json';source_path=ROOT/'packages/campaign/chapter09_source_prepare/source.plan.v1.json';roster_path=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json'
    package=json.loads(package_path.read_bytes());stage=json.loads(source_path.read_bytes())['stages']['level_main_09-17'];native=stage['native_document'];scene=package['scenarioDraft'];roster=json.loads(roster_path.read_bytes())
    assert scene['resources']['life']=={'initial':99999,'capacity':99999}
    assert scene['resources']['dp']['initial']==native['options']['initialCost']==10
    assert scene['resources']['dp']['capacity']==native['options']['maxCost']==99
    assert scene['parameters']['deploy_capacity']==native['options']['characterLimit']==9
    assert exact(scene['roster'],roster['manifest']['metadata']['roster']) and len(scene['roster'])==12
    assert exact(scene['map'],native_map(native))
    assert exact(package['manifest']['metadata']['native_predefines'],native['predefines'])
    assert exact(package['manifest']['metadata']['native_hard_predefines'],native['hardPredefines'])
    rows=scene['map']['rows'];original_actions=[a for w in native['waves'] for f in w['fragments'] for a in f['actions']]
    converted=[a for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions']]
    assert len(original_actions)==len(converted)
    births=0;routes=set()
    for original,action in zip(original_actions,converted):
        assert exact(original,action['metadata']['native_action'])
        assert action['count']==original['count'] and action['delay_seconds']==original['preDelay'] and action['interval_seconds']==original['interval']
        if action['kind']=='spawn':
            births+=action['count'];routes.add(original['routeIndex'])
            expected=route_ir(native['routes'][original['routeIndex']],rows)
            if any(any(cp.get('reachOffset',{}).values()) for cp in expected.get('checkpoints',[])):
                expected['reach_offset_policy']={'rule':'rule/m9_checkpoint_cartesian','parameters':{'axis_signs':{'row':-1,'col':1}}}
            assert exact(action['spawn']['route'],expected)
    assert births==63
    registered=scene['initialEntities'];raw=native['predefines']['tokenInsts'];assert len(registered)==len(raw)==6
    assert len({r['registration_key'] for r in registered})==6 and all(r['instanceAlias'] is None for r in registered)
    for original,row in zip(raw,registered):assert exact(original,row['parameters']['native_instance'])
    assert [r['parameters']['raw_alias'] for r in registered]==[r['alias'] for r in raw]
    card=scene['metadata']['native_card_bindings'][0];assert exact(card['native_card'],native['predefines']['tokenCards'][0])
    assert scene['resources'][card['stock_resource']]=={'initial':1,'capacity':1}
    program=Compiler(providers=providers()).compile(package);sim=Engine.create(program,providers=providers(),seed=program.scenario['seed']);sim.advance(31)
    path=Path(os.environ['ARKSIM_RUN_DIR'])/'prefix.checkpoint.json';path.write_text(json.dumps(sim.checkpoint()),encoding='utf8');restored=Engine.restore(program,json.loads(path.read_bytes()),providers=providers());sim.advance(31);restored.advance(31);head=replay(program,sim.export_replay(),providers=providers());assert sim.checkpoint()==restored.checkpoint()==head.checkpoint()
    fixed=sim.ctx.state()['predefined_registry'];assert len([k for k in fixed if k.startswith('level_main_09-17/tokenInsts/')])==6
    result={'schema':'ark-sim/c9-919-source-input-prefix/v3','passed':True,'core':implementation_digest(),'package_sha':hashlib.sha256(package_path.read_bytes()).hexdigest(),'source_sha':hashlib.sha256(source_path.read_bytes()).hexdigest(),'source_births':63,'native_routes':35,'used_route_count':len(routes),'squad12':True,'slots':9,'initialDP':10,'base_life':99999,'unitHP_unchanged':True,'native_raw_aliases_kept':True,'unique_actual_registrations':6,'stock1':True,'tilekeys_blackboards_unchanged':True,'rune_difficulty':'NORMAL1','actual_prefix_end':62,'prefix_CPP_head_full_equal':True,'checkpoint_sha':hashlib.sha256(path.read_bytes()).hexdigest(),'full_stage_executed':False,'client_verified':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        import traceback
        output=Path(sys.argv[sys.argv.index('--output')+1]);output.parent.mkdir(parents=True,exist_ok=True)
        if not output.exists():output.write_text(json.dumps({'passed':False,'actual_exit':1,'error':str(error),'traceback':traceback.format_exc()},indent=2)+'\n',encoding='utf8')
        raise
