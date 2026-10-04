"""Source-bound story acknowledgements and exact AV Opera node timelines."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter08_stage_controls/source/story_opera.source.v1.json'
OUT = ROOT / 'packages/campaign/chapter08_stage_controls/controls.module.v1.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source = json.loads(SOURCE.read_bytes())
    assert sha(SOURCE) == 'a0ff4b5f9e3e73dc62e07d3f690c5803b1ff1dc66270262c8ff649303d08bbe5'
    story = source['story']
    popup = [row for row in story['commands'] if row['command'] == 'PopupDialog']
    assert len(popup) == 8
    header = story['commands'][0]
    assert 'is_autoable=false' in header['raw']
    steps = []
    for index, row in enumerate(popup):
        steps.append({'kind': 'effects', 'effects': [{'op': 'emit', 'target': 'battle',
                      'event': 'source.story.popup.observed', 'payload': {'story_key': story['key'],
                          'index': index, 'raw_command': row}}]})
        steps.append({'kind': 'ack', 'key': 'popup/' + str(index), 'metadata': {'source_line': row['line']}})
    blocker = story['commands'][-1]
    assert blocker['command'] == 'Blocker' and 'fadetime=0.3' in blocker['parameter_text']
    steps.append({'kind': 'effects', 'effects': [{'op': 'emit', 'event': 'source.story.blocker.observed',
                                                 'payload': {'raw_command': blocker}}]})
    steps.append({'kind': 'delay', 'seconds': .3})
    controls = [{'id': 'control/ch8/source/story/main_08-17', 'kind': 'control',
                 'clock_policy': 'logical', 'ack_policy': 'external', 'steps': steps,
                 'metadata': {'native_story_key': story['key'], 'native_story_source': source['source_urls']['story'],
                              'source_payload_sha': story['fixed_payload_sha256'],
                              'reference_policy': 'Eightactualpublic acknowledgements; .3blocker fade aslogicaldelay, renderer/clientclock feedback pending'}}]
    opera_ids = {}
    for key, command in source['opera']['commands'].items():
        assert key in ('blast_effect_x', 'blast_effect_y')
        nodes = command['parsed_nodes']
        assert {node['$type'].split('.')[-1] for node in nodes} == {'CameraShake', 'ColorGrading', 'GlobalAudio'}
        assert command['raw']['operaNodes']['SerializedObjectReferences'] == [] and command['completion_seconds'] == 3
        timeline = sorted([(node['_preDelay'], index, node) for index, node in enumerate(nodes)])
        position = 0
        steps = []
        for at, index, node in timeline:
            if at > position:
                steps.append({'kind': 'delay', 'seconds': at - position})
            steps.append({'kind': 'effects', 'effects': [{'op': 'emit', 'target': 'battle',
                          'event': 'source.opera.node.observed', 'payload': {'key': key, 'node_index': index,
                              'node_class': node['$type'], 'source_node': node}}]})
            position = at
        steps.append({'kind': 'delay', 'seconds': 3 - position})
        identifier = 'control/ch8/source/opera/' + key
        opera_ids[key] = identifier
        controls.append({'id': identifier, 'kind': 'control', 'clock_policy': 'logical', 'ack_policy': 'immediate',
                         'steps': steps, 'on_complete': [{'op': 'emit', 'event': 'source.opera.completed', 'payload': {'key': key}}],
                         'metadata': {'source_key': key, 'source_asset': source['opera']['asset_path'],
                                      'source_command': command, 'completion_seconds': 3,
                                      'reference_policy': 'Eachrequest independent; renderer-onlyshake random doesnot consume battleRNG; exact0/.2/.3 and3 completion. NativeglobalLock arbitration unknown'}})
    return {'schemaVersion': 2, 'manifest': {'id': 'package/ch8/stage_controls_v1', 'requires': ['preset/ark_standard'],
            'metadata': {'source_locks': {str(path.resolve()): sha(path) for path in (SOURCE, Path(__file__))},
                         'story_bindings': {story['key']: controls[0]['id']}, 'opera_bindings': opera_ids,
                         'source_version': source['version_policy'], 'whole_stage_executed': False, 'client_verified': False}},
            'controls': controls}


if __name__ == '__main__':
    p = build()
    assert not OUT.exists()
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'sha': sha(OUT), 'controls': len(p['controls'])}))
