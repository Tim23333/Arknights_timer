"""Real frame/source attribute reads and target state boundary tests, no source numeric changes."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from tools.chapter07_ordinary.test_sotihd_v2 import package,make,deploy
def hits(s):return [e for e in s.session.events if e['type']=='damage.accepted']
def test_actual_target_DEF_current_at_hit():
 s=make();deploy(s);s.session.advance(10);s.ctx.set('blocker',('attributes','base','def'),300);s.session.advance(15);assert len(hits(s))==1 and hits(s)[0]['payload']['amount']==50 and hits(s)[0]['time']==19
def test_ASPD3_exact_source18frames_divided_to6():
 s=make();s.ctx.attributes.add_modifier('source','attack_speed_ratio',2,layer='flat',key='authored_target_speed_probe');deploy(s);s.session.advance(15);started=[e for e in s.session.events if e['type']=='ability.started'];assert len(hits(s))==1 and hits(s)[0]['time']-started[0]['time']==6 and hits(s)[0]['payload']['amount']==250
def test_dead_and_targetfree_blocker_not_hit_or_replaced_by_unblocked_other():
 s=make();deploy(s);s.session.advance(10);s.ctx.lifecycle.retire('blocker','withdrawn');s.session.advance(25);assert not hits(s)
 s=make();deploy(s);s.session.advance(10);s.ctx.set('blocker',('selection_state','target_free'),True);s.session.advance(25);assert not hits(s)
def test_first_genuine_source_route_and_HP_remain_real():
 s=make();s.session.advance(10);assert s.ctx.resources.current('source','hp')==2900 and s.ctx.get('source',('spatial','position'))['col']>0;assert not hits(s)
