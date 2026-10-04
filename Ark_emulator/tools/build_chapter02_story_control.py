"""Source-backed logical lifecycle for 2-10's native tutorial story."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'packages/campaign/chapter02_sources/native.reference.json'
OUT=ROOT/'packages/campaign/chapter02_stage_models/controls.reference_model.json'
SOURCE_SHA='97447895b3edc69f0f60113ea96bc240c25c0fe980897614e93a94dd75e0d492'


def build():
    from tools.build_chapter01_controls import audit_story
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:raise ValueError('Frozen chapter2 story source drift')
    stage=json.loads(raw)['stages']['level_main_02-10'];controls=[]
    for key,story in stage['stories'].items():
        audited=audit_story(story);rows=audited['classified_rows']
        if [row['command'] for row in rows]!=['HEADER','PopupDialog','PopupDialog','Blocker']:
            raise ValueError('Unconverted chapter2 story command sequence')
        steps=[]
        for row in rows:
            steps.append({'kind':'effects','effects':[{'op':'emit','target':'battle','event':'reference.story.row_observed',
                'payload':{'story_key':key,'native_row':deepcopy(row),'policy':'declared logical immediate acknowledgement; visual UI remains metadata'}}]})
            if row['command']=='PopupDialog':steps.append({'kind':'ack','key':'line/'+str(row['line'])})
        lock={'op':'input_lock','target':'battle','parameters':{'key':key,'enabled':True}}
        unlock=deepcopy(lock);unlock['parameters']['enabled']=False
        controls.append({'id':'control/reference/story/main_02-10','kind':'control','clock_policy':'logical','ack_policy':'immediate',
            'steps':steps,'on_start':[lock],'on_complete':[unlock],'on_cancel':[deepcopy(unlock)],
            'metadata':{'native_story_key':key,'native_story_source':deepcopy(story['source']),
                        'payload_sha256':story['payload_sha256'],'classified_rows':rows,
                        'native_wall_clock_pause_ui_verified':False,
                        'declared_policy':'Story preserves managed lifetime/input lock/ack steps; PopupDialog acknowledged immediately; Blocker visual fadetime is metadata, not combat delay.'}})
    return {'schemaVersion':2,'manifest':{'id':'package/chapter02_reference_story_control','requires':['preset/ark_standard'],
        'metadata':{'source_locks':{'packages/campaign/chapter02_sources/native.reference.json':SOURCE_SHA},
            'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'audit_helper_sha256':hashlib.sha256((ROOT/'tools/build_chapter01_controls.py').read_bytes()).hexdigest(),
            'actual_client_verified':False}},'controls':controls}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    result=build();raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Chapter2 story control changed')
    else:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'control_count':len(result['controls'])}))
