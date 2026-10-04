from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m50_deploy_stock_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter03_crate_module import build


def test_actual_native_crate_cards_stats_overlay_and_public_withdraw():
    p=build();p['scenarioDraft']={'id':'scene/test/crate_source','ruleset':'ruleset/ark_standard','roster':['unit/ch3/crate'],
        'objectives':{},'resources':{'dp':{'initial':100,'capacity':100},'crate_cards':{'initial':5,'capacity':5}},'map':{'rows':1,'cols':3}}
    s=Engine.create(Compiler().compile(p),seed=5013)
    original_mask=s.ctx.spatial.grid.tile(0,1)['passableMask']
    s.submit({'action':'deploy','definition':'unit/ch3/crate','alias':'crate','position':{'row':0,'col':1}},at=0);s.advance(1)
    assert s.ctx.resources.current('system/battle','crate_cards')==4
    assert s.ctx.resources.current('crate','hp')==100
    assert s.ctx.get('crate',('selection_state','category'))==4
    assert s.ctx.resources.current('system/battle','dp')==95
    tile=s.ctx.spatial.grid.tile(0,1)
    assert tile['buildableType']==0 and tile['passableMask']==original_mask and tile['obstacleLikeMoveCost']
    s.submit({'action':'withdraw','source':'crate'},at=1);s.advance(1)
    assert s.ctx.resources.current('system/battle','crate_cards')==4
    assert s.ctx.resources.current('system/battle','dp')==97.5
    assert not s.ctx.state()['terrain']['layers']
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_declared_obstacle_cost_can_detour_without_rewriting_passable_mask():
    p=build();p['scenarioDraft']={'id':'scene/test/crate_cost','ruleset':'ruleset/ark_standard','roster':['unit/ch3/crate'],
        'objectives':{},'resources':{'dp':{'initial':100,'capacity':100},'crate_cards':{'initial':5,'capacity':5}},'map':{'rows':2,'cols':4}}
    s=Engine.create(Compiler().compile(p));s.submit({'action':'deploy','definition':'unit/ch3/crate','position':{'row':0,'col':1}},at=0)
    s.submit({'action':'deploy','definition':'unit/ch3/crate','position':{'row':0,'col':2}},at=151);s.advance(152)
    route=s.ctx.spatial.grid.path({'row':0,'col':0},{'row':0,'col':3})
    assert {'row':0,'col':1} not in route and {'row':0,'col':2} not in route
    assert any(pos['row']==1 for pos in route)
    assert s.ctx.spatial.grid.passable(0,1) and s.ctx.spatial.grid.passable(0,2)
    assert s.ctx.resources.current('system/battle','crate_cards')==3
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
