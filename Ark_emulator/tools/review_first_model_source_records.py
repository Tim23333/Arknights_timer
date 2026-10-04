"""Read original JSON/Unity fields independently of the conversion builder."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()


def pointer(value,path):
    if not path:
        return value
    if not path.startswith('/'):
        raise ValueError('JSON pointer must be absolute')
    for token in path[1:].split('/'):
        key = token.replace('~1','/').replace('~0','~')
        value = value[int(key)] if isinstance(value,list) else value[key]
    return value


def review():
    import UnityPy
    audit_path = ROOT/'packages/campaign/conversion_drafts/main_00-10.audit.json'
    draft_path = ROOT/'packages/mainline/main_00-10.json'
    original_path = ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json'
    files = [audit_path,draft_path,original_path,Path(__file__)]
    before = {str(p):sha(p) for p in files}
    audit = json.loads(audit_path.read_bytes())
    for record in audit['source_locks']:
        path = ROOT/record['path']
        assert sha(path) == record['sha256'], 'Source lock changed: '+str(path)
    json_groups,unity_groups = defaultdict(list),defaultdict(list)
    for record in audit['field_audit']:
        kind = record['pointer_kind']
        groups = json_groups if kind == 'json_pointer' else unity_groups
        assert kind in {'json_pointer','unity_object_pathid_and_typetree_field'}
        groups[str((ROOT/record['source_path']).resolve())].append(record)
    checked_json,checked_unity = 0,0
    for path,records in json_groups.items():
        actual = json.loads(Path(path).read_bytes())
        for record in records:
            value = pointer(actual,record['native_pointer'])
            assert identity(value) == record['native_value_sha256'] == identity(record['value']), record['native_pointer']
            checked_json += 1
    actual_objects = []
    for path,records in unity_groups.items():
        requested = {int(r['native_pointer'].split('/')[2]) for r in records}
        trees = {obj.path_id:obj.read_typetree() for obj in UnityPy.load(path).objects if obj.path_id in requested}
        assert set(trees) == requested, 'Original Unity object missing'
        for record in records:
            parts = record['native_pointer'].split('/')
            value = pointer(trees[int(parts[2])],'/'+ '/'.join(parts[3:]))
            assert identity(value) == record['native_value_sha256'] == identity(record['value']), record['native_pointer']
            checked_unity += 1
        actual_objects.append({'source_path':path,'source_sha256':sha(Path(path)),
            'actual_object_path_ids':sorted(trees)})
    original = json.loads(original_path.read_bytes());draft = json.loads(draft_path.read_bytes())
    for key in ('entities','abilities','buffs','selectors','rules'):
        assert draft[key] == original[key], 'Conversion changed executable definitions: '+key
    scene = dict(draft['scenarioDraft']);source_scene = dict(original['scenarioDraft'])
    scene.pop('metadata',None);source_scene.pop('metadata',None)
    assert scene == source_scene, 'Conversion changed executable scenario'
    meta = original['manifest']['metadata']
    declarations = meta['dependency_source']
    assert declarations['native_level_sha256'] == sha(ROOT/'packages/campaign/native_reference/level_main_00-10.json')
    assert declarations['operator_normalized_sha256'] == sha(ROOT/'packages/campaign/operators.normalized.json')
    squad = meta['squad_model']
    for name, expected in squad['source_packages'].items():
        assert expected == sha(ROOT/f'packages/campaign/skills.{name}.json')
    for name, expected in squad['talent_source_packages'].items():
        assert expected == sha(ROOT/f'packages/campaign/talents.{name}.json')
    assert squad['base_model_sha256'] == sha(ROOT/'packages/campaign/units.base.json')
    after = {str(p):sha(p) for p in files}
    assert before == after
    return {'schema':'ark-sim/first-model-original-field-review/v1','passed':True,
        'identity_at_start':before,'identity_at_completion':after,'identity_stable':True,
        'json_fields_read':checked_json,'unity_fields_read':checked_unity,
        'raw_unity_objects':actual_objects,'source_locks_checked':len(audit['source_locks']),
        'classified_field_counts':dict(Counter(r['classification'] for r in audit['field_audit'])),
        'executable_definitions_and_scenario_unchanged':True,
        'historical_recipe_source_declarations_match_actual_files':True,
        'scope':'Original source values, object identities, byte locks and executable-copy checks; semantic consumers require separate review',
        'formal_approval':False,'native_fields_verified_flag_changed':False,
        'tests':[{'path':Path(__file__).relative_to(ROOT).as_posix(),'source_sha256':sha(Path(__file__)),'result':'passed'}]}


if __name__ == '__main__':
    result = review()
    output = ROOT/'validation/campaign/first_model_original_fields_root_review_20261002.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':True,'json_fields':result['json_fields_read'],'unity_fields':result['unity_fields_read'],'output':str(output)}))
