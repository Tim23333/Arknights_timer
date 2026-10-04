"""Execute fixed source draft through real public commands and disk checkpoint."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CAND=ROOT.parent/'unpack_work/campaign_finish_timeline_wave_v4_candidate'
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter07_strength_melee.policies_v2 import providers as strength
from tools.chapter07_predefines.policies_v1 import providers as ore
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert implementation_digest()=='4f16ac4c8ec0c0080302dfa1b6b1b6cc4da90d383ae9a2da5f796551d630c346'
    source=ROOT/'packages/campaign/chapter07_stage_models/level_main_07-15.native_draft.v1.json'
    assert sha(source)=='77d416b5c848194582ec30383acfc53159f5296f527938781fc4ac0fc09decbe'
    out=ROOT/'validation/campaign/chapter07_join_prefix_v1';out.mkdir(exist_ok=False)
    commands=[{'at':0,'action':{'action':'deploy','entity':'unit/char_151_myrtle','row':6,'col':3,'facing':'up','alias':'ch7_myrtle'}},
              {'at':300,'action':{'action':'skill','source':'ch7_myrtle','ability':'ability/campaign_myrtle_s2'}}]
    reg={**strength(),**ore()};program=Compiler(providers=reg).compile(source)
    s=Engine.create(program,seed=program.scenario['seed'],providers=reg)
    for command in commands:s.submit(command['action'],at=command['at'])
    s.advance(200);cp=out/'source200.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin),providers=reg)
    s.advance(400);r.advance(400);h=replay(program,s.export_replay(),providers=reg)
    assert s.checkpoint()==r.checkpoint()==h.checkpoint()
    outcomes=[thaw(e) for e in s.session.events if e['type'] in ('command.accepted','command.rejected')]
    assert len(outcomes)==2 and all(e['type']=='command.accepted' for e in outcomes)
    ore_actions=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']=='ability/ch7/predefined/ore/pulse']
    assert len(ore_actions)>=2
    assert len(program.scenario['roster'])==12
    births=[e for e in s.session.events if e['type']=='entity.created' and 'enemy' in s.ctx.entity(e['payload']['target'])['tags']]
    (out/'input.commands.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf8')
    (out/'replay.json').write_text(json.dumps(s.export_replay(),indent=2)+'\n',encoding='utf8')
    path=out/'verification.json';path.write_text(json.dumps({'passed':True,'core':implementation_digest(),
        'source_package_sha':sha(source),'checkpoint_sha':pin,'command_outcomes':outcomes,
        'actual_enemy_births_to600':len(births),'actual_ore_starts_to600':len(ore_actions),
        'events':len(s.session.events),'checkpoint_and_head_equal':True,
        'full_stage':False,'formal_admitted':False,
        'scope':'Actual exact-native 37birth draft first600tick/source2predefinedore/fixed12selected/Myrtledeployskill realDP, persistentCP200/head. Remainingenemy/sourcegates and fullprocess not inferred.'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'sha':sha(path),'events':len(s.session.events),'passed':True,'whole_stage':False}))


if __name__=='__main__':main()
