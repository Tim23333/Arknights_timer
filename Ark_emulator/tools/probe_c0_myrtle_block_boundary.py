"""Read-only current counterexample and in-memory generic control hypothesis."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def scene(proposed=False):
    path=ROOT/'packages/campaign/mainline_models/level_main_00-10.m10.json'
    data=json.loads(path.read_bytes())
    data['scenarioDraft'].update(id='scenario/c0_myrtle_block_probe',map={'rows':9,'cols':12},waves=[],scheduledEffects=[],objectives={},
        initialEntities=[{'definition':'unit/char_151_myrtle','instanceAlias':'myrtle','position':{'row':4,'col':4},
            'components':{'resources':{'sp':{'initial':24}}}},
            {'definition':'unit/enemy_1000_gopro','instanceAlias':'enemy','position':{'row':4,'col':4},
                'route':{'motionMode':'WALK','endPosition':{'row':4,'col':8}}}])
    if proposed:
        ability=next(a for a in data['abilities'] if a['id']=='ability/campaign_myrtle_s2')
        zero=ability['timeline'].pop(0)
        assert zero['at']==0 and zero['effect']['buff']=='buff/campaign_myrtle_no_block'
        ability['activation']['on_start']=[zero['effect']]
        ability['parameters']['cancel_pending_attacks']=True
        buff=next(b for b in data['buffs'] if b['id']=='buff/campaign_myrtle_no_block')
        buff['control']={'block':False}
    return data,path


def run(proposed=False,held=False):
    from ark_sim import Compiler,Engine
    from ark_sim.contracts import thaw
    data,path=scene(proposed)
    sim=Engine.create(Compiler().compile(data))
    if held:
        sim.advance(1)
        assert sim.ctx.spatial.blocked_by(sim.session.world.resolve('enemy'))==sim.session.world.resolve('myrtle')
    sim.submit({'action':'skill','source':'myrtle','ability':'ability/campaign_myrtle_s2'})
    sim.advance(25)
    enemy=sim.session.world.resolve('enemy')
    relevant=[thaw(e) for e in sim.session.events if e['type'] in ('command.accepted','command.rejected','blocking.changed','ability.started','damage.accepted','buff.applied','ability.interrupted')]
    attacks=[e for e in relevant if e['type']=='ability.started' and e['payload']['source']==enemy]
    return {'proposed_only_in_memory':proposed,'held_block_before_command':held,'program_fingerprint':sim.program.fingerprint,
        'runtime_fingerprint':sim.runtime_fingerprint,'enemy_attack_starts':[e['time'] for e in attacks],
        'final_blocked_by':sim.ctx.spatial.blocked_by(enemy),'events':relevant,'replay_inputs':sim.export_replay(),
        'fixture_scenario':thaw(sim.program.scenario),'original_package_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    from ark_sim.adapters.api import implementation_digest
    source=ROOT/'packages/campaign/skills.myrtle.json';native=json.loads(source.read_bytes())['manifest']['metadata']
    buff_component=next(c for c in native['native_skill_prefab']['components'] if c.get('pathID')==7458720872929114507)
    before=implementation_digest()
    original=run();proposed=run(True);held=run(True,True)
    assert original['enemy_attack_starts']==[1]
    assert proposed['enemy_attack_starts']==[]
    assert held['enemy_attack_starts']==[1] # Synchronous buff exists but old blocking link is still sampled.
    result={'schema':'ark-sim/c0-myrtle-block-boundary-review/v1','implementation_sha256':before,
        'implementation_stable':before==implementation_digest(),'original':original,'generic_control_hypothesis':proposed,
        'generic_control_existing_block_hypothesis':held,'native_prefab_component':buff_component,
        'native_enum_evidence':native['native_enum_evidence'],'native_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'primary_or_packages_modified':False,'current_model_gap':True,'held_block_sync_still_required':True,'formal_approval':False}
    output=ROOT/'validation/campaign/c0_myrtle_block_boundary.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'original_enemy_start':original['enemy_attack_starts'],'proposed_enemy_start':proposed['enemy_attack_starts'],
        'held_proposed_enemy_start':held['enemy_attack_starts'],'implementation_sha256':before,'output':str(output)}))


if __name__=='__main__':main()
