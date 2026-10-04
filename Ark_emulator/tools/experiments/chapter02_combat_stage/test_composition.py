import json
from pathlib import Path

from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

ROOT=Path(__file__).resolve().parents[3]


def test_actual12variant_scene_story_and_healing_fields_saved_continuation(tmp_path):
    p=json.loads((ROOT/'packages/campaign/chapter02_stage_models/level_main_02-10.m48.combat_guard.reference_model.json').read_bytes())
    scene=p['scenarioDraft'];program=Compiler().compile(p)
    actions=[a for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions']]
    assert sum(a['count'] for a in actions if a['kind']=='spawn')==36
    assert sum(a['count'] for a in actions if a['kind']=='control')==2
    assert len(scene['roster'])==12
    for uid in scene['roster']:
        assert program.definitions[uid]['components']['resources']['hp']['recovery_rule']=='rule/ch2/tile_hp_ratio_recovery'
    assert len([d for d in program.definitions.values() if d['kind']=='entity' and 'enemy' in d.get('tags',[])])==12
    s=Engine.create(program,seed=scene['seed']);s.advance(100)
    assert set(s.ctx.state()['tile_fields'])=={'1:4','1:7','4:4','5:6'}
    assert len([e for e in s.session.events if e['type']=='reference.story.row_observed'])==4
    assert not s.ctx.state().get('input_locks')
    assert s.ctx.state()['pending_waves']==36
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin))
    s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
