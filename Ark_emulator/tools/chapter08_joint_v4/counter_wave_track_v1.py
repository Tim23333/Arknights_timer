"""Execute literal source tracking request against the current generic contract."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_chapter08_joint_v4_candidate'
SOURCE = ROOT / 'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json'
OUT = ROOT / 'validation/campaign/chapter08_wave_track_source_counter_v1/report.json'


def main():
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.domains.timeline import validate_finish_request
    source = json.loads(SOURCE.read_bytes())
    template = source['BSON']['templates']['track_at_next_wave_when_buff_finish']
    node = template['parsed']['eventToActions']['ON_BUFF_FINISH'][0]
    effect = {'op': 'finish_timeline_wave', 'target': 'source', 'parameters': {
        'finish_and_skip': node['_finishAndSkip'], 'track_source_at_next_wave': node['_trackSourceAtNextWave'],
        'track_source_wave_delta': node['_trackSourceAtWaveDelta'],
        'track_all_managed_at_next_wave': node['_trackAllManagedEnemiesAtNextWave']}}
    assert effect['parameters'] == {'finish_and_skip': False, 'track_source_at_next_wave': True,
                                     'track_source_wave_delta': 0, 'track_all_managed_at_next_wave': False}
    errors = []
    try:
        validate_finish_request(effect)
    except ValueError as error:
        errors.append({'action': 'native_request_validation', 'type': type(error).__name__, 'message': str(error)})
    package = {'schemaVersion': 2, 'manifest': {'id': 'package/track/source_counter', 'requires': ['preset/ark_standard']},
               'entities': [{'id': 'unit/track/source', 'kind': 'entity', 'components': {'spatial': {},
                             'buffs': {'initial': ['buff/track/native']}}}],
               'buffs': [{'id': 'buff/track/native', 'kind': 'buff', 'on_remove': [effect]}],
               'scenarioDraft': {'id': 'scene/track/source_counter', 'ruleset': 'ruleset/ark_standard',
                                 'map': {'rows': 1, 'cols': 1}, 'initialEntities': [{'definition': 'unit/track/source',
                                 'position': {'row': 0, 'col': 0}}]}}
    try:
        Compiler().compile(package)
    except ValueError as error:
        errors.append({'action': 'actual_compilation', 'type': type(error).__name__, 'message': str(error)})
    assert len(errors) == 2 and all('Unimplemented timeline finish flag combination' in row['message'] for row in errors)
    result = {'core': implementation_digest(), 'source': str(SOURCE),
              'source_sha': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'template_document_sha': template['document_sha256'], 'native_node': node,
              'input': package, 'literal_request': effect, 'actual_errors': errors,
              'source_required_generic_gap': True, 'whole_stage_approved': False,
              'scope': 'Literal tracking=true rejects before runtime; no dropped source flag or fabricated execution'}
    OUT.parent.mkdir(exist_ok=False)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': hashlib.sha256(OUT.read_bytes()).hexdigest(), 'core': result['core'], 'errors': errors}))


if __name__ == '__main__':
    main()
