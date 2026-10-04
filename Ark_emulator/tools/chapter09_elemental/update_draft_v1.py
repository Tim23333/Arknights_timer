"""Complete the author's un-frozen draft after its saved first test failure."""
from pathlib import Path
import json
from build_candidate_v1 import OUT,ROOT,replace,sha,core

def main():
    assert core(OUT)=='872bde122b4e30849b14791e094f565c8855b4a9ef01e4f3ef01a0964badc7eb'
    folder=ROOT/'validation/campaign/chapter09_elemental_v1'
    old=folder/'initial_author_failure.json';assert not old.exists()
    old.write_text(json.dumps({'core':core(OUT),'tests_passed':15,'tests_failed':3,
        'failures':['Compiler amount_rule incorrectly inherited resource.recovery contract; two atomic packet cases rejected before execution.',
                    'Author kill fixture omitted lifecycle policy and used unsupported amount override; real damage fixture corrected to source60*scale40.'],
        'candidate_frozen':False},indent=2)+'\n',encoding='utf-8')
    compiler=OUT/'ark_sim/content/compiler.py'
    replace(compiler,'                    if key in expected_contracts and isinstance(child, str) and child in definitions:',
        "                    if value.get('op')=='elemental_damage':expected_contracts['amount_rule']='elemental.packet'\n                    if key in expected_contracts and isinstance(child, str) and child in definitions:")
    lifecycle=OUT/'ark_sim/domains/lifecycle.py'
    replace(lifecycle,'        has_initial_clocks=has_initial_clocks or needs_arbitration_atomic(definition,kwargs.get("component_overrides") or {})',
        '        has_initial_clocks=has_initial_clocks or needs_arbitration_atomic(definition,kwargs.get("component_overrides") or {})\n        has_initial_clocks=has_initial_clocks or "elemental" in definition.get("components", {}) or "elemental" in (kwargs.get("component_overrides") or {})')
    print(core(OUT))

if __name__=='__main__':main()
