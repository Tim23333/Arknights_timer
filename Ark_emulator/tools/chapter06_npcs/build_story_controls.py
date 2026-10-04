"""Actual five UTF8 story payloads, external public acknowledgement required."""
import base64,hashlib,json,re
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter06_predefines/source.reference.json'
OUT=ROOT/'packages/campaign/chapter06_npcs/story_controls.model.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    source=json.loads(SOURCE.read_bytes());controls=[];rows=[]
    for key,story in source['stories'].items():
        raw=base64.b64decode(story['payload_base64'],validate=True)
        if hashlib.sha256(raw).hexdigest()!=story['payload_sha256']:raise ValueError('Story payload identity differs')
        script=raw.decode('utf8',errors='strict');steps=[];dialogue=0
        for number,text in enumerate(script.splitlines(),1):
            if not text.strip():continue
            match=re.fullmatch(r'\[([A-Za-z_]+)(?:\((.*?)\))?\]\s*(.*)',text)
            if match is None or match[1] not in {'HEADER','PopupDialog','Blocker'}:raise ValueError('Unknown exact story command')
            row={'story_key':key,'native_line':number,'command':match[1],'raw_parameters':match[2], 'text':match[3],
                 'raw_utf8':text,'payload_sha256':story['payload_sha256']}
            rows.append(row)
            steps.append({'kind':'effects','effects':[{'op':'emit','target':'battle','event':'source.story.row','payload':row}]})
            if match[1]=='PopupDialog':
                dialogue+=1;steps.append({'kind':'ack','key':key+'/line/'+str(number)})
        lock={'op':'input_lock','target':'battle','parameters':{'key':key,'enabled':True}};unlock=deepcopy(lock);unlock['parameters']['enabled']=False
        controls.append({'id':'control/ch6/'+key.rsplit('/',1)[-1],'kind':'control','clock_policy':'logical','ack_policy':'external',
            'on_start':[lock],'on_complete':[unlock],'on_cancel':[deepcopy(unlock)],'steps':steps,
            'metadata':{'native_story_key':key,'native_story_source':deepcopy(story['source']),'payload_sha256':story['payload_sha256'],
                'native_dialogue_count':dialogue,'visual_blocker_fade_preserved_as_metadata':True}})
    assert len(controls)==5 and sum(c['metadata']['native_dialogue_count'] for c in controls)==7
    return {'schemaVersion':2,'manifest':{'id':'package/ch6/native_story_controls','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{str(SOURCE.relative_to(ROOT)):sha(SOURCE)},'builder_sha':sha(Path(__file__)),
        'policy':'Logical external dialogue ack; all native rows and managed control lifetime retained. One-tick user response adapter separate from native wall-clock/pause semantics.',
        'whole_stage_executed':False,'client_verified':False}},'controls':controls,'sourceRows':rows}


def main():
    assert not OUT.exists();OUT.parent.mkdir(parents=True,exist_ok=True);before=sha(SOURCE);value=build();assert sha(SOURCE)==before
    OUT.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(OUT),'controls':len(value['controls']),'dialogues':sum(c['metadata']['native_dialogue_count'] for c in value['controls'])}))


if __name__=='__main__':main()
