import json
from pathlib import Path

from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter02_birth_contact_adapter import build
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

ROOT=Path(__file__).resolve().parents[1]


def test_actual_source_born_airdrop_on_contact_tile_defers_until45(tmp_path):
    p=build();hole=json.loads((ROOT/'packages/campaign/chapter02_tiles/m41.hole.profile.json').read_bytes())
    p['rules']+=hole['rules'];unit=p['entities'][0]
    p['scenarioDraft']={'id':'scene/test/ch2_birth_contact','ruleset':'ruleset/ark_standard','objectives':{},
        'map':{'rows':1,'cols':1,'tiles':[{'tileKey':'tile_hole','buildableType':0,'passableMask':3}],
               'tile_mechanics':hole['tile_mechanics']},
        'initialEntities':[{'definition':unit['id'],'instanceAlias':'born','position':{'row':0,'col':0}}]}
    s=Engine.create(Compiler().compile(p),seed=4213);s.advance(44)
    assert s.ctx.alive('born') and s.ctx.resources.current('born','hp')==1450
    assert not any(e['type']=='tile.contact_death' for e in s.session.events)
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(s.program,load_bound(cp,pin))
    s.advance(2);restored.advance(2)
    assert not s.ctx.alive('born') and s.ctx.resources.current('born','hp')==0
    assert [e['time'] for e in s.session.events if e['type']=='tile.contact_death']==[45]
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay()).snapshot()
