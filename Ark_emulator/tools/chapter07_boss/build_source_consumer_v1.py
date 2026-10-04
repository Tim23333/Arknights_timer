"""Freeze a new Patriot content identity without changing the verified definitions."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'packages/campaign/chapter07_boss/patrt'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parent = OUT / 'releasewave.mechanism.v1.json'
    content = json.loads(parent.read_bytes())
    content['manifest']['id'] = 'package/ch7/patrt/source_consumer_v1'
    meta = content['manifest']['metadata']
    meta['parent_content'] = {'path': str(parent), 'sha256': sha(parent)}
    meta['source_consumer_builder_sha256'] = sha(Path(__file__))
    meta['consumer_scope'] = 'Exact patrt/a53 variant: phase0 four hits, one true rebirth, retained shared Aura, owned waiting Immo, phase1 Spear, source ON_BUFF_FINISH ReleaseWave, and parameter-sensitive invulnerability.'
    meta['unconsumed_required_mechanisms'] = ['Root ore/mine joint public integration and independent admission pending']
    meta['verification_identity'] = 'campaign_finish_timeline_wave_v4_candidate / 4f16ac4c8ec0c0080302dfa1b6b1b6cc4da90d383ae9a2da5f796551d630c346; new content must execute under its own identity'
    target = OUT / 'source.consumer.v1.json'
    target.write_bytes((json.dumps(content, ensure_ascii=False, indent=2) + '\n').encode())
    assert {k:v for k,v in content.items() if k != 'manifest'} == {k:v for k,v in json.loads(parent.read_bytes()).items() if k != 'manifest'}
    print(json.dumps({'path':str(target),'sha256':sha(target),'definition_bytes_semantically_unchanged':True,'stage_export_allowed':False}))

if __name__ == '__main__':
    main()
