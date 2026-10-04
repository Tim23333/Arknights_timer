import hashlib
import json
from pathlib import Path

from tools.audit_reference_stage_input import audit

ROOT=Path(__file__).resolve().parents[1]


def test_actual_new_stage_passes_and_old_airdrop_missing_motion_rejected():
    new=audit(ROOT/'packages/campaign/chapter02_stage_models/level_main_02-09.m44.source_closed_v3.json')
    old=audit(ROOT/'packages/campaign/chapter02_stage_models/level_main_02-09.m44.reference_model.json')
    assert new['passed'] and len(new['source_locks_checked'])==8
    assert not old['passed']
    assert {f['definition'] for f in old['failures']}=={
        'unit/chapter02/enemy_1013_airdrp/level_0/20e3225f73e1c6e6',
        'unit/chapter02/enemy_1013_airdrp_2/level_0/8903647724c13db5'}


def test_actual_source_byte_drift_and_missing_source_rejected(tmp_path):
    source=tmp_path/'source.json';source.write_bytes(b'{"value":1}')
    package={'manifest':{'metadata':{'source_locks':{'source.json':hashlib.sha256(source.read_bytes()).hexdigest()}}},'definitions':[]}
    path=tmp_path/'package.json';path.write_text(json.dumps(package),encoding='utf8')
    assert audit(path,tmp_path)['passed']
    source.write_bytes(b'{"value":2}');assert audit(path,tmp_path)['failures']==[{'path':'source.json','reason':'source_drift'}]
    source.unlink();assert audit(path,tmp_path)['failures']==[{'path':'source.json','reason':'missing_source'}]
