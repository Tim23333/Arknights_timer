"""Preserve author tests; rewrite only candidate path and sibling import."""
import json
from prepare_candidate import ROOT, OUT, REPORT, sha


def main():
    dest = ROOT/'tools/experiments/m26'; dest.mkdir(parents=True, exist_ok=True)
    rows = []
    for folder, name in [('m24','test_decisions.py'), ('m24','test_native_profiles.py'), ('m25_eligibility','test_eligibility.py')]:
        source = ROOT/'tools/experiments'/folder/name; target = dest/name
        text = source.read_text(encoding='utf8')
        text = text.replace('campaign_m24_enemy_fsm_candidate', OUT.name).replace('campaign_m25_eligibility_candidate', OUT.name)
        text = text.replace('tools.experiments.m24.test_decisions', 'tools.experiments.m26.test_decisions')
        target.write_text(text, encoding='utf8', newline='\n')
        rows.append({'source': str(source.relative_to(ROOT)), 'source_sha256':sha(source),
                     'copy':str(target.relative_to(ROOT)), 'copy_sha256':sha(target),
                     'changes': 'runtime candidate name and sibling test import only; assertions unchanged'})
    (REPORT/'test_source_copies.json').write_text(json.dumps(rows, indent=2)+'\n', encoding='utf8', newline='\n')


if __name__ == '__main__':
    main()
