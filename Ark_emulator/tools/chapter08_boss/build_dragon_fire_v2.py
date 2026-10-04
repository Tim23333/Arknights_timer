"""Source Attribute26 initial status-duration multiplier, explicit pending dynamics."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter08_boss.build_dragon_fire_v1 import OUT as PARENT,APPLICATION
from tools.chapter08_boss.build_talula_threshold_v3 import sha
OUT=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v2.json'

def build():
    assert sha(PARENT)=='eaf1a220f4a77fb598228cbb31342c96e587e1a6190662bd1f27ea7ad9c86b02'
    p=json.loads(PARENT.read_bytes());dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';text=dump.read_text(encoding='utf8')
    for line in ('public const AttributeType ONE_MINUS_STATUS_RESISTANCE = 26;','public const float MIN_ONE_MINUS_STATUS_RESISTANCE = 0.001;','public const float MAX_ONE_MINUS_STATUS_RESISTANCE = 1000;'):assert line in text
    rule=next(r for r in p['rules'] if r['id']==APPLICATION);rule['parameters'].update(duration_attribute='one_minus_status_resistance',minimum_multiplier=.001,maximum_multiplier=1000)
    rule['implementation']['provider']='reference.c8.dragon_fire.application_initial_resistance'
    m=p['manifest']['metadata'];m['source_locks'].update({x.relative_to(ROOT).as_posix():sha(x) for x in (PARENT,Path(__file__),Path(__file__).with_name('dragon_fire_policies_v2.py'))})
    m['duration_enum_source']={'path':str(dump),'sha':sha(dump),'type':26,'minimum':.001,'maximum':1000}
    m['reference_policy']['initial_duration']='StatusResistable1 parent initial duration30.5 multiplied by effective target ONE_MINUS_STATUS_RESISTANCE26, absent uses1 and sourceclamps. Changes after application need explicit future remaining-lifetime consumer; not falsely dynamic.'
    p['manifest']['id']='package/ch8/dragon_fire/source_v2';return p
if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(sha(OUT))
