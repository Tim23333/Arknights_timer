"""Strict offline intermediate trace comparison, without accuracy self-approval.

Inputs are normalized traces and an explicit comparison contract. This tool
does not read devices, infer frame alignment, round numbers, or fill gaps.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'ark-sim/intermediate-trace/v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def integer(value, label):
    if type(value) is not int:
        raise ValueError(label+' must be an integer')
    return value


def exact(left,right):
    """Compare nested JSON without bool/int or int/float equivalence."""
    if type(left) is not type(right):
        return False
    if isinstance(left,dict):
        return left.keys()==right.keys() and all(exact(left[k],right[k]) for k in left)
    if isinstance(left,list):
        return len(left)==len(right) and all(exact(a,b) for a,b in zip(left,right))
    if isinstance(left,float) and (not math.isfinite(left) or not math.isfinite(right)):
        return False
    return left==right


def index(trace):
    if trace.get('schema') != SCHEMA:
        raise ValueError('Unknown intermediate trace schema')
    rows = {}
    for sample in trace['samples']:
        frame = integer(sample['frame'], 'frame')
        if frame in rows:
            raise ValueError('Duplicate frame')
        if integer(sample['frame_before'],'frame before') != frame or integer(sample['frame_after'],'frame after') != frame or sample['complete'] is not True:
            raise ValueError('Incomplete or mixed-frame sample')
        if not isinstance(sample['values'], dict):
            raise ValueError('Sample values must be a flat explicit field map')
        rows[frame] = sample['values']
    return rows


def compare(native, model, contract):
    if contract.get('schema') != 'ark-sim/intermediate-comparison-contract/v1':
        raise ValueError('Unknown comparison contract schema')
    for key in ('stage_id','game_build','platform','content_identity','roster_identity','commands_identity','episode_identity'):
        if not isinstance(contract['identity'].get(key), str) or not contract['identity'][key]:
            raise ValueError('Required identity missing: '+key)
        if native['identity'].get(key) != contract['identity'][key] or model['identity'].get(key) != contract['identity'][key]:
            raise ValueError('Trace identity differs: '+key)
    if native.get('origin') not in ('actual_game','synthetic_test') or model.get('origin') != 'ark_sim':
        raise ValueError('Trace origins must be explicit')
    native_rows, model_rows = index(native), index(model)
    mapping = contract['time_mapping']
    if not isinstance(mapping.get('evidence'), str) or not mapping['evidence']:
        raise ValueError('Time mapping evidence required')
    numerator = integer(mapping['numerator'],'time numerator'); denominator = integer(mapping['denominator'],'time denominator')
    if numerator <= 0 or denominator <= 0:
        raise ValueError('Time mapping ratio must be positive')
    native_origin = integer(mapping['native_origin'],'native origin'); model_origin = integer(mapping['model_origin'],'model origin')
    frames = contract['native_frames']; fields = contract['fields']
    if not isinstance(frames,list) or not isinstance(fields,list):
        raise ValueError('Explicit frame and field lists required')
    for frame in frames:
        integer(frame,'covered frame')
    if not frames or len(set(frames)) != len(frames) or not fields:
        raise ValueError('Explicit nonempty unique frame and field coverage required')
    if frames != sorted(frames):
        raise ValueError('Comparison frames must be ordered')
    names = [f['name'] for f in fields]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate comparison field')
    for field in fields:
        if not all(isinstance(field.get(k),str) and field[k] for k in ('name','native_key','model_key')):
            raise ValueError('Explicit field name and native/model keys required')
        if field['mode'] not in ('exact','absolute_tolerance'):
            raise ValueError('Unknown field comparison mode')
        if field['mode'] == 'absolute_tolerance':
            tolerance = field['tolerance']
            if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or tolerance < 0 or not field.get('evidence'):
                raise ValueError('Tolerance requires finite nonnegative value and explicit evidence')
            if field.get('semantic_type') not in ('continuous_coordinate','numeric_measurement'):
                raise ValueError('Tolerance is not permitted for discrete fields')
    diffs = []; compared = 0; aligned = []
    for nf in frames:
        integer(nf,'covered frame')
        mf = Fraction((nf-native_origin)*numerator,denominator)+model_origin
        if mf.denominator != 1:
            diffs.append({'native_frame':nf,'reason':'model_time_not_representable','model_frame_fraction':str(mf)}); continue
        mf = int(mf); aligned.append({'native_frame':nf,'model_frame':mf})
        if nf not in native_rows or mf not in model_rows:
            diffs.append({'native_frame':nf,'model_frame':mf,'reason':'missing_sample'}); continue
        for field in fields:
            name = field['name']; nk = field['native_key']; mk = field['model_key']
            if nk not in native_rows[nf] or mk not in model_rows[mf]:
                diffs.append({'native_frame':nf,'model_frame':mf,'field':name,'reason':'missing_field'}); continue
            left, right = native_rows[nf][nk], model_rows[mf][mk]; compared += 1
            delta = None
            if field['mode'] == 'exact':
                accepted = exact(left,right)
            else:
                if type(left) not in (int,float) or type(right) not in (int,float) or not math.isfinite(left) or not math.isfinite(right):
                    accepted = False
                else:
                    delta = right-left; accepted = abs(delta) <= field['tolerance']
            if not accepted:
                diffs.append({'native_frame':nf,'model_frame':mf,'field':name,'reason':'value_mismatch',
                              'native':left,'model':right,'difference':delta})
    return {'schema':'ark-sim/intermediate-comparison-result/v1','comparison_passed':not diffs,
            'origin':native['origin'],'identity':contract['identity'],'compared_values':compared,
            'covered_frames':frames,'covered_fields':names,'aligned_frames':aligned,
            'differences':diffs,'first_difference':diffs[0] if diffs else None,
            'actual_game_accuracy_verified':False,'formal_approved':False,
            'scope':'Only explicitly declared samples and fields; independent source/capture review still required',
            'uncovered_requirements':contract.get('uncovered_requirements',[])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',type=Path,required=True); parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--contract',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); inputs = [args.native,args.model,args.contract,Path(__file__)]
    before = {str(p.resolve()):sha(p) for p in inputs}
    result = compare(load(args.native),load(args.model),load(args.contract))
    result['sources'] = before; result['sources_at_completion'] = {str(p.resolve()):sha(p) for p in inputs}
    if before != result['sources_at_completion']:
        raise ValueError('Comparison inputs changed')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'comparison_passed':result['comparison_passed'],'compared_values':result['compared_values'],
                      'differences':len(result['differences']),'actual_game_accuracy_verified':False}))
    raise SystemExit(0 if result['comparison_passed'] else 1)


if __name__ == '__main__':
    main()
