import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter05_sources/native.reference.json'
PIN='323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5'
def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==PIN
    source=json.loads(SOURCE.read_bytes());vid='enemy_1508_faust@0/86350d42c005ccb6';variant=source['variants'][vid]
    prefab=source['prefabs'][variant['prefab_key']];animations=source['animations'][variant['prefab_key']]['parsed']
    subset={key:component for key,component in prefab['components'].items() if component['native_class'] in {
        'RangedAttack','AdvancedSelector','EnemySkill','PassiveBuffAbility','Talent','LevelBranchTrigger','AnimatedActionToOwnerAbility','SelectorTrigger','CircleRange'}}
    parsed=[]
    for component in subset.values():
        actions=component['raw'].get('_actions',{})
        if actions.get('SerializedState'):parsed.extend(json.loads(actions['SerializedState']))
    assert any(n['$type'].endswith('MoveNextLevelBranch') for n in parsed)
    report={'schema':'ark-sim/chapter05/faust-runtime-input-audit/v1','source_locks':{str(SOURCE.relative_to(ROOT)):PIN},
        'variant':variant,'components':subset,'animation_events':animations,'decoded_actions':parsed,
        'projectiles':{k:v for k,v in source['projectiles'].items() if k in ('projectile_faust','projectile_faust_s1')},
        'required_consumers':['150second invincible damage gate + permanent blockFree/immuties',
            'normal and critical physical projectile attack at authoredframe40, interval5,criticalscale2/CD17/init17',
            'SummonBallis Skill_2 frame27/50duration + init15/CD30 higherpriority1,MoveNext7phase10predefs',
            'explicit branch availability facts/eligibility with no cast after exhaustion',
            'actual ballista skill/movement/collision consumers and retained hidden predefines'],
        'runtime_created':False,'whole_stage_executed':False,'client_verified':False}
    target=ROOT/'packages/campaign/chapter05_boss/faust/source.audit.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({'sha':hashlib.sha256(target.read_bytes()).hexdigest(),'source_variant':vid,'actions':len(parsed)}))
if __name__=='__main__':main()
