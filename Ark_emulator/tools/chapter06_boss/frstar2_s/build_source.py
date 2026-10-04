"""Freeze exact story variant; ordinary Boss is not an implementation input."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'packages/campaign/chapter06_boss/frstar2_s'
NATIVE=ROOT/'packages/campaign/chapter06_sources/native.reference.json'
VID='enemy_1510_frstar2_s@0/2ca10c3158df0a8d'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    n=json.loads(NATIVE.read_bytes());v=n['variants'][VID];p=n['prefabs'][v['prefab_key']]
    a=v['native_enemy']['resolved']['attributes'];assert type(a['maxHp']) is int and a['maxHp']==95000
    assert v['modes'][0]['nodes']['_attackTrigger']['native_class']=='NeverTrigger'
    blood=n['bson_templates']['templates']['periodic_damage_without_modify']
    node=blood['parsed']['eventToActions']['ON_BUFF_TRIGGER'][0]
    assert node['_damageWithoutModify'] is True and node['_ignoreForSp'] is True and node['_attackType']=='BUFF'
    keys={c['script_key'] for c in p['components'].values() if c.get('script_key')}
    closure={'schema':'ark-sim/ch6-frstar2-story-source-closure/v1','source_reference_sha256':sha(NATIVE),'source_locks':n['source_locks'],'variant':v,'prefab':p,'animation':n['animations'][v['prefab_key']], 'monoscripts':{k:n['native_monoscripts'][k] for k in keys},'bson':{'periodic_damage_without_modify':blood,'e2c_frozen_atkscale':n['bson_templates']['templates']['e2c_frozen_atkscale']},'profile':{'normal':'NeverTrigger; no normal automatic attack even with eligible blocker','rebirth':'No RebornTalent in this exact prefab; do not inherit ordinary phase2','blood':'permanent owned non-control-sensitive timer; waitFirstTriggerInterval1; every1s PURE NoSourceDamage2000 BUFF without_modify true ignoreSP true','skills':'IceBurst priority1 init16 cooldown1000 Skill3 effect87/full110 radius3.299999952; IceShield priority2 init23 cooldown1000 Skill1 effect55/full90 max3','immunity':'Only resolved true defined source immunities; undefined rows retained, not claimed native false','exit':'native lifePointReduce1; stage special exit counting separately owned by Root'},'reference_policies':{'tile_filter':'Deployment-eligible radius2 cells excluding occupancy; selector body unavailable, explicit replaceable policy','skill_clock':'Independent cooldowns source castLikeAttack0; full-animation shared busy policy','periodic_boundary':'First tick at1second after actual buff application; cadence source interval1'},'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'source.closure.json';path.write_bytes((json.dumps(closure,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(path),'sha256':sha(path)}))
if __name__=='__main__':main()
