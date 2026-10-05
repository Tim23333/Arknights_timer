"""Correct an inferred cannon gap without rewriting any native source record."""
import json
import hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def main():
    source = ROOT / 'packages/campaign/chapter10_source_prepare/source.detail.v2.json'
    correction = ROOT / 'validation/campaign/chapter10_source_prepare/gunctrl.scope.correction.v1.json'
    before = json.loads(source.read_bytes())
    corrected = json.loads(correction.read_bytes())
    assert corrected['native_selector_filter']['enum'] == 'FilterUtil.FilterType.BLOCK_COUNT_DES'
    assert corrected['native_selector_filter']['value'] == 42
    assert before['actual_gaps'][2] == 'Gunctrl global unique ability/current blocker-or-maxHP cannon selection and owned target lifecycle need source consumer design'
    after = json.loads(source.read_bytes())
    after['actual_gaps'][2] = ('Gunctrl global unique ability uses native FilterType42 BLOCK_COUNT_DES '
                             '(current effective block count); owned target lifecycle and declared area eligibility need source consumers')
    after['inference_scope_revision'] = {'parent': str(source), 'parent_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'correction': str(correction), 'correction_sha256': hashlib.sha256(correction.read_bytes()).hexdigest(),
        'raw_native_records_changed': False, 'runtime_completion_claimed': False}
    audit = json.loads(json.dumps(after))
    audit.pop('inference_scope_revision')
    audit['actual_gaps'][2] = before['actual_gaps'][2]
    assert audit == before
    output = source.with_name('source.detail.v3.json')
    output.write_text(json.dumps(after, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'output': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'raw_source_changes': 0}))


if __name__ == '__main__':
    main()
