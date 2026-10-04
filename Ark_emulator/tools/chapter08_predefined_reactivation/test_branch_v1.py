"""Actual native35 activations across7phases, real25sdevices no durationoverride."""
import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter08_flame_device.build_module_v2 import OUT,UNIT
from tools.chapter08_flame_device.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2]

def test_seven_native_phases_reuse10keys35realHP_SP_incarnations_CP_head(tmp_path):
    p=json.loads(OUT.read_bytes());profile=json.loads((ROOT/'packages/campaign/chapter08_consumers/flame/predefines.profile.v2.json').read_bytes());branch=json.loads((ROOT/'packages/campaign/chapter08_consumers/flame/branch.profile.v2.json').read_bytes())
    p['entities'].append({'id':'unit/branch/director','kind':'entity','components':{'spatial':{},'abilities':['ability/branch/advance']}})
    p['abilities'].append({'id':'ability/branch/advance','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'advance_branch','parameters':{'branch':'bsnake_flame'}}]},'timeline':[]})
    # Nativepositions are exact; this controlledsource test uses floor map for
    # device-only branch scheduling, not the main08-17 fullstage map.
    p['scenarioDraft']={'id':'scene/flame/nativebranch','ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':15},
        'branches':branch['runtime_branch'],'initialEntities':profile['initial_entities']+[{'definition':'unit/branch/director','instanceAlias':'director','position':{'row':0,'col':0}}]}
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg)
    for i in range(7):s.submit({'action':'skill','source':'director','ability':'ability/branch/advance'},at=1500*i)
    s.advance(1550);cp=tmp_path/'branch1550.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(8250);r.advance(8250);head=replay(program,s.export_replay(),providers=reg)
    assert s.checkpoint()==r.checkpoint()==head.checkpoint() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    activated=[e for e in s.session.events if e['type']=='entity.activated'];assert len(activated)==35
    assert len([e for e in s.session.events if e['type']=='projectile.launched'])==140
    assert not [e for e in s.session.events if e['type']=='command.rejected']
    for key,row in s.ctx.state()['predefined_reactivation'].items():assert row['activations']==row['profile']['max_activations']
