"""Exact native key/source profile needed by the frozen stage converter."""
import json
from pathlib import Path
from tools.chapter07_predefines.build_ore_v1 import ROOT, SOURCE, sha


def main():
    folder=ROOT/'packages/campaign/chapter07_predefines_consumer'
    p=json.loads((folder/'story.controls.v1.json').read_bytes())
    source=json.loads(SOURCE.read_bytes())
    key='obt/tutorial/level/main_07-16'
    meta=p['controls'][0]['metadata']
    meta.update(native_story_key=key,native_story_source=source['stories'][key]['source'])
    p['manifest']['id']='package/ch7/story_controls/v2'
    p['manifest']['metadata']['source_locks'][str(Path(__file__).resolve())]=sha(Path(__file__))
    out=folder/'story.controls.v2.json';assert not out.exists()
    out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(out)}))


if __name__=='__main__':main()
