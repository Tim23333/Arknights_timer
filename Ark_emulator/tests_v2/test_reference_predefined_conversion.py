from copy import deepcopy
import json
from pathlib import Path
import pytest
from tools.build_reference_stage_scenario_v2 import compose
ROOT=Path(__file__).resolve().parents[1]


def source():return json.loads((ROOT/'packages/campaign/native_reference/level_main_03-07.json').read_bytes())


def binding(raw):return {r['id']:{'unit':'unit/source/'+r['id'],'motion':'WALK'} for r in raw['enemyDbRefs']}


def profile(raw):
    native=raw['predefines'];sensor=native['tokenInsts'][0];card=native['tokenCards'][0]
    return {'native_predefines':deepcopy(native),'initial_entities':[{'definition':'unit/test_sensor','position':{'row':3,'col':3},'facing':'up',
            'parameters':{'native_bucket':'tokenInsts','native_instance':deepcopy(sensor)}}],
        'card_bindings':[{'native_bucket':'tokenCards','native_card':deepcopy(card),'definition':'unit/test_crate','stock_resource':'crate_cards'}],
        'resources':{'crate_cards':{'initial':5,'capacity':5}}}


def test_native_sensor_and_five_cards_preserved_with_preview_control_count():
    raw=source();scene,controls=compose(raw,'main_03-07',binding(raw),{},predefined_profile=profile(raw))
    assert len(scene['initialEntities'])==1
    assert scene['metadata']['native_predefines']==raw['predefines']
    assert scene['resources']['crate_cards']['initial']==5
    actions=[a for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions']]
    assert sum(a['count'] for a in actions if a['kind']=='spawn')==61
    assert sum(a['count'] for a in actions if a['kind']=='control')==5
    assert sum('reference.route_preview.observed'==e['event'] for c in controls for step in c['steps'] for e in step.get('effects',[]))==2
    # This is a source conversion audit only; dummy unit definitions cannot
    # compile or become a stage proof until the actual dependencies are joined.


@pytest.mark.parametrize('mutation',[lambda p:p['initial_entities'].clear(),lambda p:p['card_bindings'].clear(),
    lambda p:p['native_predefines']['tokenCards'][0].update(initialCnt=4),lambda p:p['resources'].update(dp={'initial':99999}),
    lambda p:p['resources']['crate_cards'].update(initial=4),lambda p:p['initial_entities'][0]['position'].update(row=4)])
def test_missing_or_changed_native_consumers_reject(mutation):
    raw=source();p=profile(raw);mutation(p)
    with pytest.raises(ValueError):compose(raw,'main_03-07',binding(raw),{},predefined_profile=p)
