"""New source identity closes independently discovered burn reference conflict."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_behavior_restart_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from tools.chapter08_boss.talula_skill_policies_v3 import providers
PARENT=ROOT/'packages/campaign/chapter08_consumers/boss/talula.restart.v3.reference.json'
FIRE=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v3.json'
OUT=ROOT/'packages/campaign/chapter08_consumers/boss/talula.restart.burn.v4.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert sha(PARENT)=='869a8138e8fbe0dd5048de50286698ce22fc8a8b568952ec5ccb8f4227eccad0' and sha(FIRE)=='d8c834d1d832b88a0c933e8169a2c0713e36a9454dc126144f2d940f09b3a0ab'
    p,f=[json.loads(x.read_bytes()) for x in (PARENT,FIRE)]
    for group in ('rules','buffs'):
        ids={d['id'] for d in f[group]};p[group]=[d for d in p[group] if d['id'] not in ids]+f[group]
    m=p['manifest']['metadata'];m['source_locks'].update(f['manifest']['metadata']['source_locks']);m['source_locks'].update({str(x):sha(x) for x in (PARENT,FIRE,Path(__file__),ROOT/'tools/chapter08_boss/talula_skill_policies_v3.py')})
    m['burn_reference_policy']=f['manifest']['metadata']['reference_policy'];m['source_policy_corrections']=['Previous burnparentlive noop/reset-aftergap230 rejected by independent source; current parentrefresh and childreset with retainedhandle. Oldsource tests retain originalidentity not completeBossapproval.']
    p['manifest']['id']='package/ch8/talula/restart_burn_v4';x=deepcopy(p);x['scenarioDraft']={'id':'scene/talula/burn4/compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':0,'col':0}}]};Compiler(providers=providers()).compile(x);return p
if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(sha(OUT))
