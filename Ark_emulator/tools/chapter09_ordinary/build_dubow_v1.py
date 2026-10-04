"""Exact C9 archer recipe, one owned attack for the shared combat/attack node."""
import json
import sys
from pathlib import Path
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter09_ordinary.build_melee_v1 import SOURCE,PLAN,OUT,CORE,sha
RANGE=SOURCE.with_name('dubow.range.supplement.v1.json')
OUTFILE=OUT/'enemy_1167_dubow.module.v1.json'


def providers():
    from tools.chapter08_bsnake_combat.policies_v1 import providers as registry
    return registry()


def build():
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.domains.selection import DEFAULT_STATE
    assert implementation_digest()==CORE
    assert sha(SOURCE)=='592afac29cc32d1aeaba3ea739eb6da5a218055e255a42f53315f4a2ca0962ff'
    assert sha(RANGE)=='6d3ee3811216cede53fc1fd07a882c2be308db20ec8571bbba37d7d677c1947d'
    data=json.loads(SOURCE.read_bytes());vid,v=next((k,v) for k,v in data['variants'].items() if v['prefab_key']=='enemy_1167_dubow')
    cs=data['prefabs'][v['prefab_key']]['components'];root=next(c for c in cs.values() if c['native_class']=='Enemy');mover=next(c for c in cs.values() if c['native_class']=='MoveController')
    mode=v['modes'][0];assert mode['nodes']['_combat']['path_id']==mode['nodes']['_attack']['path_id']
    attack=mode['nodes']['_attack'];raw=attack['raw'];assert attack['native_class']=='RangedAttack'
    assert (raw['_damageType'],raw['_attackType'],raw['_elementDamageType'],raw['_epDamageRatio'])==(1,1,0,0)
    selector=next(c for c in cs.values() if c['native_class']=='AdvancedSelector');cfg=deepcopy(selector['raw'])
    assert (cfg['_targetSide'],cfg['_targetMotion'],cfg['_targetCategory'],cfg['_postFilter'],cfg['_ignoreTargetFree'],cfg['_forceIgnoreCamouflage'],cfg['_maxNum'])==(2,1,1,4,0,0,1)
    assert not root['raw']['_commonAbilities'] and not mode['raw']['_generalAbilities']
    passive=v['passive_and_skill_components'];assert len(passive)==1
    inline=passive[0]['raw']['_buffs'][0];assert inline['buffKey']=='enemy_refracting' and inline['isSilenceable']==1 and inline['loadFromDB']==0
    assert v['native_enemy']['resolved']['talentBlackboard']==[{'key':'refracting.magic_resistance','value':70.0,'valueStr':None}]
    a=v['native_enemy']['resolved']['attributes'];uid='unit/ch9/dubow/'+vid.split('/')[-1];aid='ability/ch9/dubow/attack';sid='selector/ch9/dubow/range';rule='rule/ch9/dubow/'
    # Reuse the same generic refraction and source-stat recipe. Translation
    # touches IR identities only; original native records are stored separately.
    template=json.loads((OUT/'enemy_1165_duhond.module.v1.json').read_bytes())
    def replace(value):
        if isinstance(value,dict):return {key:replace(item) for key,item in value.items()}
        if isinstance(value,list):return [replace(item) for item in value]
        if isinstance(value,str):return value.replace('ch9/duhond','ch9/dubow').replace('c3aa41fce7557727',vid.split('/')[-1])
        return value
    p=replace(template);p['manifest']['id']='package/ch9/dubow/source_v1'
    meta=p['manifest']['metadata'];meta.update(source_locks={str(path):sha(path) for path in (SOURCE,PLAN,RANGE,Path(__file__))},
        native_variant=vid,native_reference=v['native_reference'],source_root=root,source_combat=attack,source_passive=passive[0],native_source_stats=a)
    meta['reference_policy'].update(attack_target='Native range2, typed enemy side/ground/category with targetfree and camouflage rejection; HATE lexical priority then recent ID reference',
        projectile='Native homing speed10/life5/retain on source retirement, current source ATK/target DEF at hit; no second attack for identical combat/attack pointers')
    body=p['entities'][0]['components'];p['entities'][0]['metadata']={'native_variant':vid,'native_reference':v['native_reference']}
    body['attributes']['base'].update(max_hp=a['maxHp'],atk=a['atk'],**{'def':a['def'],'mres':a['magicResistance']},
        move_speed=a['moveSpeed'],attack_interval=a['baseAttackTime'],attack_speed_ratio=a['attackSpeed']/100,mass_level=a['massLevel'],block_cost=root['raw']['_blockVolume'])
    body['resources']['hp']['initial']=a['maxHp'];body['abilities']=[aid];body['spatial']['steering']['parameters'].update(response_factor=mover['raw']['_steeringFactor'],max_acceleration=mover['raw']['_maxSteeringForce'])
    p['buffs'][0]['metadata']['native_inline']=inline
    p['selectors']=[{'id':sid,'kind':'selector','region':{'type':'radius','radius':2.0},'filters':[{'state':'alive'}],'limit':1,
          'eligibility':{'rule':rule+'eligible','parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}}}]
    animation=attack['animation_binding'];hit=next(e for e in animation['events'] if e['name']=='OnAttack')
    assert hit['frame']==21 and animation['duration']['frame']==45
    ability=p['abilities'][0];ability.update(id=aid,selector=sid,duration_seconds=animation['duration']['seconds']);ability['rules']['targeting.selection']=rule+'selection'
    ability['timeline'][0]['at_seconds']=hit['seconds'];ability['timeline'][0]['effect'].update(scale=raw['_atkScale'],projectile_definition='projectile/ch9/dubow')
    ability['metadata']={'source_OnAttack_frame':21,'source_full_frame':45,'one_owned_shared_native_node':True}
    behavior=p['behaviors'][0];behavior['decision']['rule']=rule+'decision';profile=behavior['decision']['profiles'][0]
    profile['selectors']=[{'key':'normal','selector':sid}];profile['cast_groups']=[{'key':'normal','abilities':[aid]}];profile['parameters'].update(blocked_target=False,stop_on_target=True)
    p['rules'] += [{'id':rule+'eligible','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}},
       {'id':rule+'selection','kind':'rule','contract':'targeting.selection','dependencies':['rule/ark_attribute_layers'],'implementation':{'type':'provider','provider':'reference.c8.bsnake.hatred'}},
       {'id':rule+'decision','kind':'rule','contract':'behavior.decision','implementation':{'type':'provider','provider':'reference.c8.bsnake.normal_decision'}},
       {'id':rule+'motion','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}},
       {'id':rule+'collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}]
    native=data['projectiles'][raw['_projectileKey']];comp=native['components'];motion=next(c['raw'] for c in comp.values() if c['native_class']=='AdvancedMovement');simple=next(c['raw'] for c in comp.values() if c['native_class']=='SimpleProjectile')
    assert (motion['_speed'],simple['_lifeTime'],simple['_maxHitNum'],simple['_stopWhenSourceInvalid'])==(10.0,5.0,1,0)
    p['projectiles']=[{'id':'projectile/ch9/dubow','kind':'projectile','motion':{'rule':rule+'motion','parameters':{'mode':'homing','speed':motion['_speed']}},
       'collision':{'rule':rule+'collision','parameters':{'enabled':False}},'lifetime_seconds':simple['_lifeTime'],'max_hits':simple['_maxHitNum'],
       'can_hit_same_target':bool(simple['_canHitSameTargetMultipleTimes']),'stop_after_max':bool(simple['_stopAfterMaxHit']),'stop_after_first':bool(simple['_stopAfterFirstHit']),
       'attach_at_launch':False,'completion_blocking':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position',
          'finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':bool(motion['_forceReachedWhenTimeup']),'hit_on_expire':bool(simple['_alwaysHitTraceTargetInTheEnd'])},
       'metadata':{'native_projectile':native}}]
    fixture=deepcopy(p);fixture['scenarioDraft']={'id':'scene/dubow/compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':uid,'position':{'row':0,'col':0}}]}
    Compiler(providers=providers()).compile(fixture);return p


if __name__=='__main__':
    p=build();assert not OUTFILE.exists();OUTFILE.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({'sha':sha(OUTFILE),'actual_compile':True,'source_radius':2.0,'owned_attack_count':1,'whole_stage':False}))
