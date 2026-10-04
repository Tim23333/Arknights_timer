"""The new content really combines frozen dependencies and source patches."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay


def read(stage,folder):
    return json.loads((ROOT/f'packages/campaign/chapter01_stage_models/{folder}/level_main_{stage}.partial.json').read_bytes())


def test_projectile_timelines_and_native_wave_geometry_not_replaced_by_old_decision_parent():
    for stage in ('01-11','01-12'):
        old,new=read(stage,'m22'),read(stage,'m26')
        assert new['scenarioDraft']['timeline']==old['scenarioDraft']['timeline']
        assert new['scenarioDraft']['map']==old['scenarioDraft']['map']
        assert new.get('projectiles')==old.get('projectiles')
        for key in ('abilities','effects','buffs'):
            assert new.get(key)==old.get(key)
        p=Compiler().compile(new)
        assert 'rule/m26/source_qualification' in p.definitions
        assert p.definitions['unit/chapter01_w']['components']['behavior']['machine'].startswith('behavior/m24/')


def test_sparse_source_literals_override_only_declared_math_and_keep_unknowns():
    for stage in ('01-11','01-12'):
        p=read(stage,'m26');units={e['id']:e for e in p['entities']}
        cannon=units['unit/campaign_weedy_cannon']['components']['selection_state']
        assert cannon['category']==2 and cannon['side']==0 and cannon['profession']==128
        emp=units['unit/chapter01_emp']['components']['selection_state'];assert emp['category']==2 and emp['profession']==256
        npc=units['unit/ch1_predefined_adnach_e0_l20']['components']['selection_state'];assert npc['motion']==1 and npc['profession']==2
        for u in units.values():
            if 'selection_state' not in u['components']:continue
            evidence=u['metadata']['m26_selection_state'];state=u['components']['selection_state']
            assert all(state[key]==value for key,value in evidence['source_literal_patch'].items())
            assert evidence['actual_client_verified'] is False
            assert 'unit_type' in evidence['math_policy_fields']
        assert 'm26_actor_unknown_getters_and_status_math_policy_client_pending' in p['manifest']['metadata']['pending_model_gaps']


def test_c4_and_normal_have_actual_distinct_enabled_motion_profiles():
    p=read('01-12','m26');selectors={s['id']:s for s in p['selectors']}
    normal=selectors['selector/chapter01_w_normal_0']['eligibility']['parameters']['source_configuration']
    c4=selectors['selector/chapter01_w_c4_0']['eligibility']['parameters']['source_configuration']
    assert normal['_targetMotion']==1 and c4['_targetMotion']==3
    assert c4['_ignoreTargetFree']==0 and normal['_ignoreTargetFree']==0
    assert all(selectors[f'selector/chapter01_w_c4_{mode}']['eligibility']['rule']=='rule/m26/source_qualification' for mode in (0,1))


def test_actual_whole_scene_prefix_compiles_runs_and_commands_replay():
    for stage in ('01-11','01-12'):
        p=read(stage,'m26');program=Compiler().compile(p);s=Engine.create(program,seed=p['scenarioDraft']['seed'])
        s.advance(15);checkpoint=s.checkpoint();r=Engine.restore(program,checkpoint);s.advance(5);r.advance(5)
        assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
        assert s.ctx.state()['finished'] is False
