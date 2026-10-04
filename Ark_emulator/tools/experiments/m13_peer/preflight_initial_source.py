"""Independent compile-context rejection for spatial/default-stat battle controls."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.experiments.m13_peer import verify as h


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--digest',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim';before=implementation_digest();assert before==args.digest
    files=[Path(__file__),Path(h.__file__)];source={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};cases=[]
    for name,region,op in [('circle',{'type':'circle','radius':1},'apply_buff'),('grid',{'type':'grid_offsets','offsets':[[0,0]]},'apply_buff'),
        ('manhattan',{'type':'manhattan','radius':1},'apply_buff'),('default_damage',{'type':'all'},'damage'),
        ('default_heal',{'type':'all'},'heal'),('push',{'type':'all'},'push')]:
        effect={'op':op,'selector':'selector/peer'}
        if op=='apply_buff':effect['buff']='buff/peer'
        if op=='push':effect['force']=1
        if op=='damage':effect['damage_type']='true'
        p=h.scene(steps=[{'kind':'effects','effects':[effect]}]);p['selectors']=[{'id':'selector/peer','kind':'selector','region':region,'limit':None}]
        p['buffs']=[{'id':'buff/peer','kind':'buff','modifiers':[]}]
        try:Compiler().compile(p)
        except ValueError as error:
            message=str(error);cases.append({'case':name,'result':'passed' if 'control/' in message else 'failed','error':message,
                'expected':'explicit control source/origin/stat context CompileError; no deferred KeyError','fixture':p})
        else:cases.append({'case':name,'result':'failed','error':'unsupported control battle source compiled'})
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};stable=source==after and before==implementation_digest();passed=stable and all(c['result']=='passed' for c in cases)
    result={'schema':'ark-sim/bounded-control-peer-review/v1','passed':passed,'implementation_sha256':before,'runtime_module':ark_sim.__file__,'cases':cases,
        'identity_stable':stable,'source_at_start':source,'source_at_completion':after,
        'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed' if passed else 'failed'}],
        'scope':'six unsupported battle-source control contexts rejected at compilation; no native/source or stage approval','formal_approval':False,'promotion_receipt':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':passed,'cases':[(c['case'],c['result'],c['error']) for c in cases]}));return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
