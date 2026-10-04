"""Literal native eighteen controls mapped without changing stage or converter."""
import json,hashlib
from pathlib import Path
from tools.chapter08_join_review.review_v2 import same
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    stage=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v1.json';plan=ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json';controls=ROOT/'packages/campaign/chapter08_stage_controls/controls.module.v1.json'
    assert sha(stage)=='905cbdd790e9ebf84607a60ec8fdbdd60a2bc2f6ee601fae74b60ae8eecf9a18'
    assert sha(controls)=='aad91ae8effb4fc75b1ea2af80c95aa371d9b3bf20ebf37d931f5477b062f1b5'
    native=json.loads(plan.read_bytes())['stages']['level_main_08-17']['native_document'];p=json.loads(stage.read_bytes());s=p['scenarioDraft'];raw=[];mapped=[]
    for wi,w in enumerate(native['waves']):
        for fi,f in enumerate(w['fragments']):
            for ai,a in enumerate(f['actions']):
                if a['actionType'] in ('STORY','PLAY_OPERA'):raw.append(((wi,fi,ai),a))
    for wi,w in enumerate(s['timeline']['waves']):
        for fi,f in enumerate(w['fragments']):
            for a in f['actions']:
                if a['kind']!='control':continue
                n=a['metadata']['native_action']
                if n['actionType'] not in ('STORY','PLAY_OPERA'):continue
                key=(wi,fi,a['metadata']['native_action_index']);original=next(v for k,v in raw if k==key)
                assert same(n,original)
                assert a['count']==n['count'] and type(a['count']) is int
                assert type(a['delay_seconds']) is float and a['delay_seconds']==n['preDelay']
                assert type(a['interval_seconds']) is float and a['interval_seconds']==n['interval']
                assert a['managed'] is n['managedByScheduler'] and a['blocks_fragment'] is n['blockFragment'] and a['blocks_wave'] is (not n['dontBlockWave'])
                expected='control/ch8/source/story/main_08-17' if n['actionType']=='STORY' else 'control/ch8/source/opera/'+n['key'];assert a['definition']==expected
                mapped.append({'native_index':key,'definition':expected,'raw_route_index':n['routeIndex'],'delay_seconds':a['delay_seconds'],'count':a['count']})
    assert len(raw)==len(mapped)==18 and len(native['waves'])==len(s['timeline']['waves'])==4
    definitions={v['id']:v for v in p['definitions']}
    for c in json.loads(controls.read_bytes())['controls']:assert same(c,definitions[c['id']])
    out=ROOT/'validation/campaign/chapter08_controls_independent_v1/stage_mapping.audit.json';assert not out.exists();out.write_bytes((json.dumps({'status':'literal18_controls_mapping_passed','stage_sha256':sha(stage),'controls_sha256':sha(controls),'source_plan_sha256':sha(plan),'mapped':mapped,'raw_metadata_type_exact':True,'scope':'Only STORY1/OPERA17 conversion and raw delay/count/flags/route identity/source-control definitions; no actor/stats/finalrestore/whole-stage approval. Current logical, independent-concurrency policies remain renderer/native-clock feedback.'},ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()
