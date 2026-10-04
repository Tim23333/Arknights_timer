"""Convert pinned UTF8 7-18 rows to explicit public-ack logical control."""
import json
from copy import deepcopy
from pathlib import Path
from tools.chapter07_predefines.build_ore_v1 import ROOT, sha


def main():
    source=ROOT/'packages/campaign/chapter07_predefines_consumer/story.requirements.v1.json'
    raw=json.loads(source.read_bytes())
    steps=[]
    for row in raw['commands']:
        steps.append({'kind':'effects','effects':[{'op':'emit','target':'battle',
            'event':'source.story.row','payload':row}]})
        if row['command']=='PopupDialog':
            steps.append({'kind':'ack','key':'main_07-16/line/'+str(row['line'])})
        elif row['command']=='Tutorial':
            steps += [{'kind':'delay','seconds':.5},
                      {'kind':'ack','key':'main_07-16/tutorial/'+str(row['line'])}]
        elif row['command']=='Blocker':
            steps.append({'kind':'delay','seconds':.3})
        elif row['command']!='HEADER':raise ValueError('Unknown source command')
    lock={'op':'input_lock','target':'battle','parameters':{'key':'main_07-16/tutorial','enabled':True}}
    unlock=deepcopy(lock);unlock['parameters']['enabled']=False
    p={'schemaVersion':2,'manifest':{'id':'package/ch7/story_controls/v1','requires':['preset/ark_standard'],
        'metadata':{'source_locks':{str(source):sha(source),str(Path(__file__).resolve()):sha(Path(__file__))},
                    'reference_policy':raw['reference_policy'],'whole_stage_executed':False,'client_verified':False}},
       'controls':[{'id':'control/ch7/main_07-16','kind':'control','clock_policy':'logical','ack_policy':'external',
        'on_start':[lock],'on_complete':[unlock],'on_cancel':[deepcopy(unlock)],'steps':steps,
        'metadata':{'source_key':'obt/tutorial/level/main_07-16','payload_sha':raw['source']['payload_sha'],
                    'actual_source_rows':7,'expected_popup_acks':4,'expected_tutorial_acks':1,
                    'protect_time_seconds':.5,'fade_time_seconds':.3}}]}
    out=ROOT/'packages/campaign/chapter07_predefines_consumer/story.controls.v1.json';assert not out.exists()
    out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(out),'rows':7,'ack_steps':5}))


if __name__=='__main__':main()
