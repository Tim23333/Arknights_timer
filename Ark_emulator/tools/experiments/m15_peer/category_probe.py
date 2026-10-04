"""Known native category mask1 excludes enemy device2; old/new outputs separate."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.experiments.m15_peer import verify as h


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,default=h.CANDIDATE);parser.add_argument('--digest',default=h.CORE)
    parser.add_argument('--package',type=Path,default=h.PACKAGE);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim' and implementation_digest()==args.digest
    h.PACKAGE=args.package.resolve();data=h.scene(sp=5)
    # Keep one missing-category ordinary enemy, one explicitDEFAULT1, and one
    # source-known TRAP_OR_ITEM2. No canonical EMP skill/selector replacements.
    prototype=next(e for e in data['entities'] if e['id']=='unit/peer_enemy')
    normal=deepcopy(prototype);normal['id']='unit/peer_explicit_default';normal['metadata']={'native_category':1}
    device=deepcopy(prototype);device['id']='unit/peer_enemy_device';device['metadata']={'native_category':2};device['tags']+=['device']
    data['entities'] += [normal,device]
    data['scenarioDraft']['initialEntities']=data['scenarioDraft']['initialEntities'][:1]+[
        {'definition':'unit/peer_enemy','instanceAlias':'missing','position':{'row':4,'col':4}},
        {'definition':normal['id'],'instanceAlias':'default','position':{'row':5,'col':6}},
        {'definition':device['id'],'instanceAlias':'enemy_device','position':{'row':4,'col':5}}]
    s=h.make(data);h.command(s,'device','ability/chapter01_emp/burst',0);s.advance(24)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];targets={e['payload']['target'] for e in hits};expected={s.session.world.resolve(x) for x in ('missing','default')}
    passed=targets==expected and s.ctx.resources.current('enemy_device','hp')==3000 and all(e['payload']['amount']==800 for e in hits)
    actual=h.finish(s,{'native_targetCategory1_DEFAULT_only':True,'missing_explicit_model_default1':True,'excludeTRAP2':True})
    files=[Path(__file__),Path(h.__file__),h.SOURCE,args.package.resolve()];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    result={'schema':'ark-sim/bounded-device-category-peer/v1','passed':passed,'implementation_sha256':args.digest,'runtime_module':ark_sim.__file__,
        'input_package_sha256':hashlib.sha256(args.package.read_bytes()).hexdigest(),'expected_target_ids':sorted(expected),'actual_target_ids':sorted(targets),
        'fixture_package':data,'actual':actual,'runtime_enemy_device':thaw(s.ctx.entity('enemy_device')),'definition_enemy_device':thaw(s.program.definitions[device['id']]),
        'source_hashes':hashes,'core_identity_stable':implementation_digest()==args.digest,'formal_approval':False,'review_receipt':False,
        'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed' if passed else 'failed'}]}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':passed,'expected':sorted(expected),'actual':sorted(targets),'deviceHP':s.ctx.resources.current('enemy_device','hp')}));return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
