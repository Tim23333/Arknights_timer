import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter03_hidden_terrain_module import build
from tools.build_reference_stage_scenario_v2 import map_plan
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3]


def test_actual_native_preplaced_sensor_rewrite_direction_sp_and_saved_replay(tmp_path):
    p=build();raw=json.loads((ROOT/'packages/campaign/native_reference/level_main_03-07.json').read_bytes())
    mp=map_plan(raw);native=raw['predefines']['tokenInsts'][0];position={'row':mp['rows']-1-native['position']['row'],'col':native['position']['col']}
    p['scenarioDraft']={'id':'scene/test/native_sensor_placement','ruleset':'ruleset/ark_standard','objectives':{},
        'map':{key:mp[key] for key in ('rows','cols','tiles')},'initialEntities':[{
            'definition':'unit/chapter03/trap_005_sensor','instanceAlias':'sensor','position':position,'facing':native['direction'].lower(),'deployed':True,
            'parameters':{'native_instance':native}}]}
    s=Engine.create(Compiler().compile(p),seed=5351);s.advance(30)
    assert s.ctx.get('sensor',('spatial','position'))==position
    assert s.ctx.get('sensor',('spatial','facing'))=='up'
    assert s.ctx.resources.current('sensor','hp')==100
    tile=s.ctx.spatial.grid.tile(position['row'],position['col']);assert tile['buildableType']==0 and tile['passableMask']==2
    assert not s.ctx.spatial.grid.passable(position['row'],position['col'])
    assert abs(s.ctx.resources.current('sensor','sp')-1)<1e-10
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
