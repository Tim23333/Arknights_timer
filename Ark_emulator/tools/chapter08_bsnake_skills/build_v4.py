"""Consume native AlwaysTrigger for explosion, SelectorTrigger for Ignite."""
import json
from pathlib import Path
from tools.chapter08_bsnake_skills.build_v1 import BASE,sha
def main():
    old=BASE/'skills.module.v3.json';p=json.loads(old.read_bytes());c=json.loads((BASE/'source.closure.v1.json').read_bytes());cs=c['prefab']['components']
    bindings=[]
    for a in p['abilities']:
        raw=a['metadata']['native_component']['component']['raw'];go=raw['m_GameObject']['m_PathID']
        skill=next(v for v in cs.values() if v.get('native_class')=='EnemySkill' and v['gameobject_path_id']==go)
        trigger=cs[str(skill['raw']['_trigger']['m_PathID'])]
        ignite='/ignite/' in a['id'];assert trigger['native_class']==('SelectorTrigger' if ignite else 'AlwaysTrigger')
        if ignite:assert trigger['raw']['_minTargetNum']==1
        a['activation']['parameters']['requires_targets']=ignite
        a['metadata']['native_EnemySkill']=skill;a['metadata']['native_trigger']=trigger
        bindings.append({'ability':a['id'],'source_trigger':trigger['native_class']})
    p['manifest']['id']='package/ch8/bsnake/skills_v4';p['manifest']['metadata']['source_locks'].update({str(x):sha(x) for x in (old,Path(__file__))})
    p['manifest']['metadata']['trigger_bindings']=bindings
    p['manifest']['metadata']['reference_policies'].append('Arbitration source EnemySkill priority0 is represented in skill class priority10 above normal class0; within class actual priority preserved. Samepriority stable owned-order remains reference.')
    out=BASE/'skills.module.v4.json';assert not out.exists();out.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()
