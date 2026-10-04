"""Full selected source Talula recipes with dynamic parent lifetime."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_buff_lifetime_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from tools.chapter08_buff_lifetime.talula_providers_v1 import providers
PARENT=ROOT/'packages/campaign/chapter08_consumers/boss/talula.restart.burn.v5.reference.json'
FIRE=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v8.dynamic.json'
OUT=ROOT/'packages/campaign/chapter08_consumers/boss/talula.dynamic.v8.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert sha(PARENT)=='fad92c36f9b5d78217f2e868cd3b9f2247e10512c348372f487d4b7f17870f56';p,f=[json.loads(x.read_bytes()) for x in (PARENT,FIRE)]
    for group in ('rules','buffs'):
        ids={d['id'] for d in f[group]};p[group]=[d for d in p[group] if d['id'] not in ids]+f[group]
    m=p['manifest']['metadata'];m['source_locks'].update(f['manifest']['metadata']['source_locks']);m['source_locks'].update({str(x):sha(x) for x in (PARENT,FIRE,Path(__file__),ROOT/'tools/chapter08_buff_lifetime/talula_providers_v1.py')});m['required_runtime']='7e76e49e8b196f1c7ec6d3a08c7760cbb4ebc7eaa02ef778f6e71c820549fef8'
    m['burn_reference_policy']=f['manifest']['metadata']['reference_policy'];m['pending_required_consumers']=['Currentcore/sourceconsumer independentreviews','Allstage requiredsource composition and fullprocess gates'];m['partial_consumer_scope']='Source chosen two-mode attacks/four skills/onceHPthreshold/restart/burnrefreshreset/dynamicresistance implemented with explicitreference timing; completeBoss admission pending independent field audit.'
    p['manifest']['id']='package/ch8/talula/dynamic_v8';x=deepcopy(p);x['scenarioDraft']={'id':'scene/talula/v6/compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':0,'col':0}}]};Compiler(providers=providers()).compile(x);return p
if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(sha(OUT))
