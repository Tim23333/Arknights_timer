"""Independent qualified-cell rule binding, effect options and runtime faults."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent / 'unpack_work/campaign_m54_qualified_visibility_candidate'
CORE = 'e6e0142c9ef9aa2cdcf35188aba0865efba370346eecf1c50750a45f56974b75'
OUT = ROOT / 'validation/campaign/m53_root_peer'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.campaign_streaming_evidence import write_canonical, observations, export_events


def state(side=0):
    return {'side': side, 'motion': 1, 'category': 1, 'profession': 0, 'unit_type': 1,
            'abnormal_flags': [], 'abnormal_combos': [], 'target_free_flags': [], 'target_free_combos': [],
            'target_free': False, 'ally_target_free': False, 'heal_free': False, 'camouflage': False,
            'can_select_camouflage': False}


def fixture(expression=None):
    cfg = {'_targetSide': 2, '_targetMotion': 3, '_targetCategory': 1, '_ignoreTargetFree': 0,
           '_onlyIgnoreSomeOfTargetFreeCase': 0, '_excludeSomeAbnormalFlags': 0, '_needProfessionMask': 0,
           '_ignoreAllyTargetFree': 0, '_ignoreHealFree': 0, '_ignoreMotionMode': 0,
           '_forceIgnoreCamouflage': 0, '_checkUnitType': 0}
    params = {'offsets': [[0,0]], 'eligibility': {'rule': 'rule/peer_eligibility', 'parameters': {
        'source_configuration': cfg, 'defaults': state(), 'side_policy': 'relative_ally_enemy', 'neutral_policy': 'reject'}}}
    rule = {'id': 'rule/peer_eligibility', 'kind': 'rule', 'contract': 'targeting.eligibility',
            'implementation': {'type': 'expression', 'expression': expression} if expression else
                              {'type': 'provider', 'provider': 'model.targeting.eligibility'}}
    entities = [{'id': 'unit/peer_caster', 'kind': 'entity', 'components': {'spatial': {},
                 'selection_state': state(1), 'attributes': {'base': {'atk': 70}}, 'abilities': ['ability/peer_area']}},
                {'id': 'unit/peer_victim', 'kind': 'entity', 'tags': ['player'], 'components': {'spatial': {},
                 'selection_state': state(), 'attributes': {'base': {'max_hp': 1000, 'def': 0, 'mres': 0}},
                 'resources': {'hp': {'initial': 1000, 'capacity': 1000, 'role': 'health'}}}}]
    return {'manifest': {'requires': ['preset/ark_standard']}, 'entities': entities,
            'rules': [rule, {'id': 'rule/peer_area', 'kind': 'rule', 'contract': 'area.members',
                            'dependencies': ['rule/peer_eligibility'], 'parameters': params,
                            'implementation': {'type': 'provider', 'provider': 'ark.area.qualified_cell_offsets'}}],
            'selectors': [{'id': 'selector/peer_primary', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'primary'}], 'limit': 1}],
            'abilities': [{'id': 'ability/peer_area', 'kind': 'ability', 'selector': 'selector/peer_primary',
                           'activation': {'mode': 'manual', 'on_start': [{'op': 'area', 'center': 'target',
                             'membership_rule': 'rule/peer_area', 'effects': [{'op': 'damage', 'damage_type': 'true'}]}]}, 'timeline': []}],
            'scenarioDraft': {'id': 'scene/peer/qualified_area', 'ruleset': 'ruleset/ark_standard', 'objectives': {}, 'map': {'rows': 5, 'cols': 5},
              'initialEntities': [{'definition': 'unit/peer_caster', 'instanceAlias': 'caster', 'position': {'row': 0,'col': 0}},
                                  {'definition': 'unit/peer_victim', 'instanceAlias': 'main', 'tags': ['primary'], 'position': {'row': 2,'col': 2}},
                                  {'definition': 'unit/peer_victim', 'instanceAlias': 'neighbor', 'position': {'row': 2.5,'col': 2}}]}}


def main():
    import ark_sim
    assert Path(ark_sim.__file__).resolve().parent == RUNTIME / 'ark_sim' and implementation_digest() == CORE
    OUT.mkdir(parents=True, exist_ok=True); cases=[]
    guards=[Path(__file__),RUNTIME/'ark_sim/domains/qualified_areas.py',RUNTIME/'ark_sim/domains/effects.py']
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards}
    scenarios=[('effect_override',fixture(),[930,930]),
               ('custom_source_and_candidate',fixture("{'accepted': inputs.source.components.attributes.base.atk == 70 and inputs.candidate.components.spatial.position.row < 2.5, 'reason': 'independent source and position condition'}"),[930,1000]),
               ('half_cell_exclusion',fixture(),[930,1000])]
    for name,p,expected in scenarios:
        if name=='effect_override':
            p['abilities'][0]['activation']['on_start'][0]['parameters']={'offsets':[[0,0],[1,0],[1,0]]}
        program=Compiler().compile(p);s=Engine.create(program,seed=5377)
        commands=[{'at':3,'action':'skill','source':'caster','ability':'ability/peer_area'}]
        s.submit({k:v for k,v in commands[0].items() if k!='at'},at=3);s.advance(2)
        directory=OUT/name;directory.mkdir(exist_ok=True);cp=directory/'checkpoint.json';pin=write_ordered(cp,s.checkpoint())
        r=Engine.restore(program,load_bound(cp,pin));s.advance(3);r.advance(3)
        actual=[s.ctx.resources.current(ref,'hp') for ref in ('main','neighbor')];assert actual==expected,(name,actual,expected)
        observed=observations(s);assert observed==observations(r)==observations(replay(program,s.export_replay()))
        assert not [e for e in s.session.events if e['type'].startswith('random.')]
        for filename,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('snapshot.json',s.snapshot())]:write_canonical(directory/filename,value)
        journal=export_events(directory/'events.jsonl',s);cases.append({'case':name,'actual_HP':actual,'expected_HP':expected,'journal':journal,'observations':observed,'durable_checkpoint_equal':True,'replay_equal':True})
    p=fixture("{'accepted': 1/0 > 0, 'reason': 'real failure'}");s=Engine.create(Compiler().compile(p),seed=5377);checkpoint=s.checkpoint()
    try:s.ctx.effects.execute('caster',['main'],p['abilities'][0]['activation']['on_start'][0])
    except Exception as error:failure={'type':type(error).__name__,'message':str(error)}
    else:raise AssertionError('Custom fault was accepted')
    assert s.checkpoint()==checkpoint
    write_canonical(OUT/'fault.input.json',p);write_canonical(OUT/'fault.checkpoint.json',checkpoint)
    cases.append({'case':'custom_actual_fault_full_rollback','error':failure,'checkpoint_equal':True})
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};assert before==after and implementation_digest()==CORE
    report={'schema':'ark-sim/qualified-area-independent-review/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),
            'source_start':before,'source_end':after,'cases':cases,'scope':'Independent pure custom child rule reads source/candidate; effect overrides; half-cell/dedup; no RNG; complete public diskCP/replay; true child fault rollback',
            'actual_client_verified':False,'whole_stage_executed':False}
    write_canonical(OUT/'final_review.json',report);print(json.dumps({'passed':True,'cases':len(cases)}))


if __name__=='__main__':main()
