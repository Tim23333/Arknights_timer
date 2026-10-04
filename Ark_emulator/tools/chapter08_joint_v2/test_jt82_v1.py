"""Actual native short scene/fields/routes/births, strict dormant-source gates."""
import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_chapter08_joint_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter08_stage_join.runner_providers_v2 import providers
from tools.chapter08_joint_v2.build_jt82_v1 import OUT,build,sha
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_stage_join.inactive_branches_v1 import compose

def test_exact_native_draft_rebuild_source32_and_fullMap():
    assert sha(OUT)=='a79a0962fe841092fc319c4df41ad3438b0b8496769ef8e9cbf7c5d77d54bda3'
    p=json.loads(OUT.read_bytes());assert p==build();assert p['manifest']['metadata']['source_births']==32
    assert p['scenarioDraft']['resources']['life']['initial']==3 and len(p['scenarioDraft']['roster'])==12
    assert len(p['scenarioDraft']['map']['tile_mechanics'])==4

def test_actual120_native_frames_durableCP_head_complete_events(tmp_path):
    p=json.loads(OUT.read_bytes());reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);s.advance(50)
    cp=tmp_path/'actual50.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(70);r.advance(70);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    assert len(s.ctx.periodic_fields.state()['fields'])==6

@pytest.mark.parametrize('change',[lambda n:n['waves'][0]['fragments'][0]['actions'][0].update(key='bsnake_flame'),
    lambda n:n['hardPredefines']['tokenInsts'].update(unexpected='token')])
def test_dormant_branch_emptyhardsource_profile_rejects_new_active_semantics(change):
    native=json.loads((ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json').read_bytes())['stages']['level_main_08-16']['native_document'];change(native)
    with pytest.raises(ValueError):compose(native,'level_main_08-16',{}, {},inactive_profile={'native_branches':native['branches'],'reason':'test','source_consumer_documents':[{}]})


def test_actual_publicplan330_onlylifeoverlay_DP_and_Myrtle_skill(tmp_path):
    from tools.campaign_runthrough_progress_v5 import validate_native_overlay
    parent=json.loads(OUT.read_bytes());overlay=OUT.with_name('level_main_08-16.native_draft.v6.life99999.v1.json');p=json.loads(overlay.read_bytes());commands=ROOT/'scenarios/campaign/chapter08/level_main_08-16/public_plan_v4/commands.json';validate_native_overlay(p,parent,commands)
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg)
    for command in json.loads(commands.read_bytes()):
        if command['at']<330:s.submit({k:v for k,v in command.items() if k!='at'},at=command['at'])
    s.advance(160);cp=tmp_path/'public160.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(170);r.advance(170);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    results=[e for e in s.session.events if e['type'] in ('command.accepted','command.rejected')];assert len(results)==2 and all(e['type']=='command.accepted' for e in results)
    assert s.ctx.resources.current('system/battle','life')==99999
