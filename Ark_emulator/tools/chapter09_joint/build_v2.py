"""Generic owned elemental callback dispatches no-source effects with None attribution."""
import json
import shutil
import sys
from pathlib import Path

from tools.chapter09_joint.build_v1 import ROOT,core,sha

BASE=ROOT.parent/'unpack_work/campaign_elemental_no_source_v1_candidate'
OUT=ROOT.parent/'unpack_work/campaign_elemental_no_source_v2_candidate'
OLD='df99d466177027c5b1905f42cd12d77bac9749240a9b1fe465fb4cddb95864fe'


def main():
    assert core(BASE)==OLD and not OUT.exists()
    shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    path=OUT/'ark_sim/domains/elemental.py';text=path.read_text()
    old="""            child=thaw(effect)
            child.setdefault('parameters',{})['elemental_break']=thaw(lease['provenance'])
            self.ctx.effects.execute(ref,[ref],child,cause=cause)"""
    new="""            child=thaw(effect)
            if child.get('op')=='no_source_damage':
                # Attribution stays None. The real owned break lineage is data
                # in origin, not actor/cast permission or a dummy zero-ATK unit.
                child.setdefault('origin',{})['elemental_break']={
                    'owner':ref,'generation':lease['generation'],
                    'provenance':thaw(lease['provenance'])}
                self.ctx.effects.execute(None,[ref],child,cause=cause)
            else:
                child.setdefault('parameters',{})['elemental_break']=thaw(lease['provenance'])
                self.ctx.effects.execute(ref,[ref],child,cause=cause)"""
    assert text.count(old)==1
    path.write_bytes(text.replace(old,new).encode('utf8'))
    identity=core(OUT);folder=ROOT/'validation/campaign/chapter09_joint_v2';folder.mkdir(parents=True,exist_ok=False)
    report={'core':identity,'parent':OLD,'parent_failed_FIRE_callback_retained':True,
        'scope':'Generic elemental owned callback no-source dispatch; explicit on_break ordering, real break provenance preserved in origin',
        'files':{str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in (OUT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')},
        'required':['source FIRE actual numbers/CP/head','own full105/base','fresh combined peer'], 'promoted':False}
    (folder/'merge.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps({'core':identity,'from_parent_changes':1,'promoted':False}))


if __name__=='__main__':main()
