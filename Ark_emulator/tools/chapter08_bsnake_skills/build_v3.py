"""Correct content expression root and bind selection at actual ability consumer."""
import json
from pathlib import Path
from tools.chapter08_bsnake_skills.build_v1 import BASE,sha
def main():
    old=BASE/'skills.module.v2.json';p=json.loads(old.read_bytes())
    for buff in p['buffs']:
        for e in buff.get('on_remove',[]):
            if e.get('condition')=='targets[0].components.runtime.alive':e['condition']='inputs.targets[0].components.runtime.alive'
    for a in p['abilities']:
        selector=next(s for s in p['selectors'] if s['id']==a['selector'])
        a['rules']['targeting.selection']=selector.pop('rules')['targeting.selection']
    p['manifest']['id']='package/ch8/bsnake/skills_v3';p['manifest']['metadata']['source_locks'].update({str(x):sha(x) for x in (old,Path(__file__))})
    out=BASE/'skills.module.v3.json';assert not out.exists();out.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()
