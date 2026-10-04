"""Source-derived corrected refresh/reset; old source-policy counter retained."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter08_boss.build_dragon_fire_v2 import OUT as PARENT
from tools.chapter08_boss.build_dragon_fire_v1 import APPLICATION,TIMER,CHILD
from tools.chapter08_boss.build_talula_threshold_v3 import sha
OUT=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v3.json'

def build():
    assert sha(PARENT)=='8bac20240654c1d24765859847011f31849330bada66192971f49a68c3cac18d'
    p=json.loads(PARENT.read_bytes());dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';text=dump.read_text(encoding='utf8');assert 'public const BuffData.OverrideType EXTEND = 3;' in text and 'public const BuffData.OverrideType EXTEND_TIME = 4;' in text
    rule=next(r for r in p['rules'] if r['id']==APPLICATION);rule['implementation']['provider']='reference.c8.dragon_fire.application_extend_reset'
    for b in p['buffs']:b['stacking']={'mode':'refresh','max_stacks':1,'identity':['definition','target']}
    m=p['manifest']['metadata'];m['source_locks'].update({str(x):sha(x) for x in (PARENT,Path(__file__),Path(__file__).with_name('dragon_fire_policies_v3.py'))})
    m['reference_policy']['lifetime']='Parent overrideType3 EXTEND interpreted as refresh remaining duration to selected30.5s, not EXTEND_TIME4 additive duration. Permanent derived child remains and no stacking. While parent live, child ramp/phase unchanged; after timer absence, same child handle reapplied generation increments/reset started_at. Fixed source enum and cited reference page support; methodbody still unverified.'
    m['reference_policy']['source_policy_correction']='Independent source review rejected oldliveparent-noop and neverreset230 aftergap. Oldv1/v2 and authorproofs retained with their own scope. Newversion uses source parentEXTEND and reference effectendreset.'
    m['reference_policy']['external_reference']={'url':'https://prts.wiki/w/%E5%A1%94%E9%9C%B2%E6%8B%89','scope':'Reference refresh-not-stack and ramp reset on effect end, corroborates fixed source; pageversion may differ and no clientproof.'}
    p['manifest']['id']='package/ch8/dragon_fire/source_v3';return p
if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(sha(OUT))
