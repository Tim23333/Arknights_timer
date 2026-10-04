"""Record native allow-SP flag versus current selected-skill resource policy."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tools.witness_canonical_roster_trio as witness


def main():
    from ark_sim.adapters.api import implementation_digest
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=witness.ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_roster.json')
    parser.add_argument('--output',type=Path,default=witness.ROOT/'validation/campaign/canonical_chen_sp_boundary.m8_roster.json')
    args=parser.parse_args();witness.PACKAGE=args.package.resolve()
    data=witness.scene([witness.actor('chen',sp=4)],enemy=None,target='chen')
    data['scenarioDraft']['waves']=[{'at':119,'definition':'unit/witness_enemy','position':{'row':4,'col':5},'instanceAlias':'enemy'}]
    sim=witness.make(data);sim.advance(122)
    observed=sim.ctx.resources.current('chen','sp')
    source=witness.read(witness.ROOT/'packages/campaign/skills.chen.json')
    wrappers=[{'pathID':c['pathID'],'class':c['class'],'fields':c['fields']} for c in source['manifest']['metadata']['native_skill_prefab']['components'] if '_allowSpRecoveryWhenAffecting' in c['fields']]
    observation=witness.finish(sim)
    result={'schema':'ark-sim/canonical-sp-policy-observation/v1','implementation_sha256':implementation_digest(),
        'input_package':str(witness.PACKAGE),'input_package_sha256':witness.sha(witness.PACKAGE),
        'selected_recipe_source_sha256':witness.sha(witness.ROOT/'packages/campaign/skills.chen.json'),
        'source_wrappers':wrappers,'stimulus':'initial4SP; actual enemy spawn119; no runtime writes',
        'actual':observation,'observed_SP_talent_during_S1':observed,
        'native_method_body_verified':False,'status':'explicit_recovery_policy_review_required',
        'formal_approval':False,'review_receipt':False}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':result['status'],'output':str(args.output),'source_allow_flags':[r['fields']['_allowSpRecoveryWhenAffecting'] for r in wrappers]}))


if __name__=='__main__':main()
