"""Source dynamic resistance applies to parent nominal clock, child independent."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_buff_lifetime_v1_candidate'));sys.path.insert(1,str(ROOT))
from tools.chapter08_boss.build_dragon_fire_v3 import OUT as PARENT
from tools.chapter08_boss.build_dragon_fire_v1 import TIMER,APPLICATION
OUT=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v4.dynamic.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert sha(PARENT)=='d8c834d1d832b88a0c933e8169a2c0713e36a9454dc126144f2d940f09b3a0ab';p=json.loads(PARENT.read_bytes());r=next(x for x in p['rules'] if x['id']==APPLICATION)
    # Application uses unscaled nominal30.5; target resistance belongs to rate.
    r['parameters']['duration_attribute']='model_unused_fixed_rate_attribute';r['parameters']['minimum_multiplier']=1;r['parameters']['maximum_multiplier']=1
    rid='rule/ch8/dragon_fire/dynamic_rate';p['rules'].append({'id':rid,'kind':'rule','contract':'buff.lifetime_rate','parameters':{'attribute':'one_minus_status_resistance','minimum':.001,'maximum':1000},'implementation':{'type':'provider','provider':'reference.c8.dynamic_buff_rate'}})
    timer=next(x for x in p['buffs'] if x['id']==TIMER);timer['lifetime']={'rule':rid,'parameters':{},'count_when_inactive':True}
    m=p['manifest']['metadata'];m['source_locks'].update({str(x):sha(x) for x in (PARENT,Path(__file__),Path(__file__).with_name('policies_v1.py'))});m['required_runtime']='b131a0bce20511a16e597e45d7ab1217186b00f81098aa125d166c8874b36698'
    m['reference_policy']['dynamic_remaining']='Nominal30.5 parent clock consumes previousinterval dt/clamp(target effective Attr26); newrate sampled currentboundary for nextinterval. Fixedchild1s/ramp realworld time unchanged. Counter initialonly915 now shouldexpire608 afterpublicresist300.'
    p['manifest']['id']='package/ch8/dragon_fire/dynamic_v4';return p
if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(sha(OUT))
