from copy import deepcopy
import json
from pathlib import Path

import pytest

from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_tile_recovery_adapter import adapt_unit
from tools.build_chapter02_tile_fields import build as fields
from tools.build_chapter02_tile_request_models import build as operands

ROOT=Path(__file__).resolve().parents[1]


def test_actual_fixed_myrtle_health_capacity_and_healing_cell_source_consumed():
    roster=json.loads((ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json').read_bytes())
    myrtle=next(d for d in roster['definitions'] if d['id']=='unit/char_151_myrtle')
    converted=adapt_unit(myrtle,{'tile':'tile_healing','source_ratio':.03})
    assert converted['components']['resources']['hp']['initial']==myrtle['components']['resources']['hp']['initial']==1565
    # Isolate field recovery from actual Myrtle's separate innate talent.
    converted['components']['buffs']={'initial':[]};converted['components']['abilities']=[];converted['components'].pop('behavior',None)
    converted['components']['resources']={'hp':converted['components']['resources']['hp']}
    converted['components']['resources']['hp']['initial']=500
    p=fields();numeric=operands()['buffs.lossless_request.model.json'];p['rules']+=numeric['rules'];p['entities'].append(converted)
    board={'HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO':.03}
    p['scenarioDraft']={'id':'scene/test/native_health_field','ruleset':'ruleset/ark_standard','objectives':{},
        'map':{'rows':1,'cols':1,'tiles':[{'tileKey':'tile_healing','buildableType':1,'passableMask':1,'blackboard':board}],
               'tile_mechanics':{'tile_healing':{'type':'occupancy_buff_field','definition':'unit/ch2/field/tile_healing','expected_blackboard':board}}},
        'initialEntities':[{'definition':converted['id'],'instanceAlias':'myrtle','position':{'row':0,'col':0}}]}
    # Remove inherited formula binding because this isolated module keeps the
    # standard attribute pipeline and consumes only the actual HP1565 value.
    converted.pop('rules',None)
    s=Engine.create(Compiler().compile(p),seed=4915);s.advance(30)
    assert s.ctx.resources.current('myrtle','hp')==pytest.approx(546.95)
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_existing_recovery_driver_is_not_silently_overwritten():
    unit={'id':'unit/test','components':{'attributes':{'base':{'max_hp':10}},'resources':{'hp':{'initial':10,'capacity':10,'role':'health','recovery_rate':1}}}}
    with pytest.raises(ValueError,match='composition'):adapt_unit(unit,{})


def test_all_fixed12_and_owned_units_keep_native_hp_abilities_and_complete_dependencies():
    from tools.build_campaign_healing_tile_roster import build
    new=build();old=json.loads((ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json').read_bytes())
    before={d['id']:d for d in old['definitions']}
    for d in new['definitions']:
        if d['kind']!='entity' or 'player' not in d.get('tags',[]):continue
        hp=d['components']['resources']['hp'];original=before[d['id']]['components']['resources']['hp']
        assert hp['initial']==original['initial']
        assert hp.get('capacity')==original.get('capacity')
        assert hp.get('capacity_attribute')==original.get('capacity_attribute')
        assert d['components'].get('abilities')==before[d['id']]['components'].get('abilities')
    numeric=operands()['buffs.lossless_request.model.json']
    scene={'id':'scene/test/healing_roster_closure','ruleset':'ruleset/ark_standard',
        'roster':new['manifest']['metadata']['roster'],'rules':new['manifest']['metadata']['stage_rules'],
        'resources':{'dp':{'initial':10,'capacity':99}}}
    program=Compiler().compile(scene,packages=[new,{'rules':numeric['rules']}])
    assert len([d for d in program.definitions.values() if d['kind']=='entity'])==15
    assert 'rule/ch2/tile_hp_ratio_recovery' in program.definitions
