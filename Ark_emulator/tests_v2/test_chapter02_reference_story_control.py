from copy import deepcopy
import json
from pathlib import Path

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.build_chapter02_story_control import build
from tools.build_reference_stage_scenario import compose
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

ROOT=Path(__file__).resolve().parents[1]


def test_source_story_managed_lifetime_lock_rows_and_durable_replay(tmp_path):
    p=build();control=p['controls'][0]
    p['scenarioDraft']={'id':'scene/test/ch2_story','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[
            {'kind':'control','definition':control['id'],'managed':True,'blocks_wave':True,'blocks_fragment':True}]},
            {'actions':[{'kind':'effects','effects':[{'op':'emit','target':'battle','event':'test.story.next_fragment'}]}]}]}]}}
    s=Engine.create(Compiler().compile(p),seed=4210);s.advance(1)
    observed=[e['payload']['native_row']['command'] for e in s.session.events if e['type']=='reference.story.row_observed']
    assert observed==['HEADER','PopupDialog','PopupDialog','Blocker']
    assert not s.ctx.state().get('input_locks')
    assert any(e['type']=='test.story.next_fragment' for e in s.session.events)
    assert s.ctx.state()['pending_waves']==0
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(s.program,load_bound(cp,pin))
    s.advance(2);restored.advance(2)
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_chapter02_story_binding_required_and_native_timing_retained():
    raw=json.loads((ROOT/'packages/campaign/native_reference/level_main_02-10.json').read_bytes())
    bindings={r['id']:{'unit':'unit/test_'+r['id'],'motion':'WALK'} for r in raw['enemyDbRefs']}
    # Test converter scheduling only: deliberately absent field definitions do
    # not compile; production uses the reviewed actual field module.
    profiles={'tile_healing':{'type':'occupancy_buff_field','definition':'unit/test_field','expected_blackboard':{'HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO':.03}}}
    with pytest.raises(ValueError,match='STORY requires'):compose(raw,'level_main_02-10',bindings,profiles)
    controls=build()['controls'];story={c['metadata']['native_story_key']:c for c in controls}
    scene,converted=compose(raw,'level_main_02-10',bindings,profiles,story_controls=story)
    actions=[a for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions']]
    assert sum(a['count'] for a in actions if a['kind']=='spawn')==36
    assert sum(a['count'] for a in actions if a['kind']=='control')==2
    assert [c['id'] for c in converted if c['metadata'].get('native_story_key')]==[controls[0]['id']]
    assert any(cp['type']=='WAIT_CURRENT_FRAGMENT_TIME' and cp['time']==82 for a in actions if a['kind']=='spawn' for cp in (a['spawn']['route'].get('checkpoints') or []))
    bad=deepcopy(story);bad[next(iter(bad))]['metadata']['native_story_key']='wrong'
    with pytest.raises(ValueError,match='key/source binding'):compose(raw,'level_main_02-10',bindings,profiles,story_controls=bad)
