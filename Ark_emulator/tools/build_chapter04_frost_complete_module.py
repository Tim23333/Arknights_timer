"""Compose actual source-bound Frost modules with declared three-skill policies."""
import argparse,hashlib,json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NORMAL_PATH='packages/campaign/chapter04_boss/frost_combat_v6/first17.bb8.reference_ground.json'
ICE_PATH='packages/campaign/chapter04_boss/ice_shield_v3/module.reference.json'
PINS={NORMAL_PATH:'8ba0c5745735b55136fa8ba49fd277a293c0664da3701b4715594cd4139c2377',
      ICE_PATH:'490b35461d4ef1e53549a97312f061264f124defefa2a962a83b0e95fb9d1e4a'}
ICE='ability/ch4/frost/ice_shield';NORMAL='ability/frost/normal';BLAST='ability/frost/blast'


def build():
    inputs={}
    for path,pin in PINS.items():
        raw=(ROOT/path).read_bytes();assert hashlib.sha256(raw).hexdigest()==pin
        inputs[path]=json.loads(raw)
    p=deepcopy(inputs[NORMAL_PATH]);ice=inputs[ICE_PATH]
    p.setdefault('definitions',[]).extend(deepcopy(ice['definitions']))
    boss=next(e for e in p['entities'] if e['id']=='unit/ch4/frstar/level0')
    boss['components']['abilities'].append(ICE)
    # Explicit reference: both enemy skills and normal attack share the current
    # attack clock; source IceShield castLikeAttack0 ambiguity remains disclosed.
    boss['components']['ability_arbitration']={'priority_order':'higher_first','busy':'all_casts',
        'entries':[{'ability':aid,'priority':priority,'attack_clock':True,
            'require_attack_control':True,'condition':'True','parameters':{}}
            for aid,priority in [(ICE,2),(BLAST,1),(NORMAL,0)]]}
    boss['components']['rebirth']['reset_cooldowns'].append({'ability':ICE,'initial_delay_seconds':30})
    profile=p['behaviors'][0]['decision']['profiles'][0]
    profile['cast_groups'].append({'key':'ice','abilities':[ICE]})
    rule=next(r for r in p['rules'] if r['id']=='rule/frost/decision')
    nodes=rule['implementation']['nodes'];byid={n['id']:n for n in nodes}
    nodes.insert(1,{'id':'ice_ready','expression':
        "inputs.clock.time >= inputs.source.components.runtime.cooldowns['"+ICE+"'] and inputs.tile_candidates['"+ICE+"'] != []"})
    byid['target']['expression']='('+byid['target']['expression']+') or nodes.ice_ready'
    byid['busy']['expression']='('+byid['busy']['expression']+') or (inputs.cast_groups.ice != [])'
    # Preserve source's explicit three clocks and frame55 event. Whole Skill
    # animation length cannot be inferred from the emission event alone.
    meta=p['manifest']['metadata']
    meta.update(source_locks=PINS,builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        full_boss_dependency_consumer=True,full_stage_executed=False,client_verified=False,
        policies={'skill_priority':'higher_first2 ice /1 blast /0 normal; accepted cooldown/target qualification before fallback',
            'shared_attack_clock':'all three use normal interval3.7s; Ice castLikeAttack0 remains explicit reference choice',
            'cast_busy':'all casts suppress subsequent casts; behavior groups suppress movement during normal/blast/ice',
            'ice_duration':'frame55 effect and finish; animation end/body not recovered, replaceable ability.duration',
            'ice_rebirth_clock':'reset30s after actual restoration; source pause/reset conflict declared',
            'ice_selection':ice['definitions'][1]['metadata']['selection_policy'],
            'ice_unknowns':ice['definitions'][1]['metadata']['source_conflict']})
    p['manifest']['id']='package/ch4/frost/complete_reference_v1'
    p['manifest']['version']='1'
    return p


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--check',action='store_true');args=ap.parse_args()
    import sys;sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim' and implementation_digest()==args.expected_core
    p=build()
    scene={'id':'scene/frost_closure','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':5},
        'initialEntities':[{'definition':'unit/ch4/frstar/level0','position':{'row':2,'col':2}}]}
    Compiler().compile(scene,packages=[p])
    data=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:assert args.output.read_bytes()==data
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('xb') as f:f.write(data)
    print(json.dumps({'core':args.expected_core,'output':str(args.output),'sha':hashlib.sha256(data).hexdigest(),'compiled':True,'full_stage_executed':False}))
if __name__=='__main__':main()
