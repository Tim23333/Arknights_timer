from copy import deepcopy
import json
from pathlib import Path
import pytest
from tools.build_reference_stage_scenario_v3 import compose
ROOT=Path(__file__).resolve().parents[3]


def fixture():
    plan=json.loads((ROOT/'packages/campaign/chapter05_plans/source.plan.json').read_bytes());native=deepcopy(plan['stages']['level_main_05-10']['native_document'])
    branches=native.pop('branches');assert len(branches['faust_ballis']['phases'])==7
    rows=len(native['mapData']['map']);pre=native['predefines']
    profile={'native_predefines':deepcopy(pre),'initial_entities':[
        {'definition':'unit/adapter_registered','position':{'row':rows-1-record['position']['row'],'col':record['position']['col']},
            'facing':record['direction'].lower(),'active':False,'registration_key':record['alias'],'instanceAlias':record['alias'],
            'parameters':{'native_bucket':'tokenInsts','native_instance':deepcopy(record)}} for record in pre['tokenInsts']],
        'card_bindings':[],'resources':{}}
    bindings={ref['id']:{'unit':'unit/source/'+ref['id'],'motion':'WALK'} for ref in native['enemyDbRefs']}
    profiles={'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}}
    return native,profile,bindings,profiles


def test_source_ten_hidden_records_become_dormant_exact_registered_actors():
    native,profile,bindings,profiles=fixture();s,c=compose(native,'level_main_05-10',bindings,profiles,predefined_profile=profile)
    assert s['metadata']['native_predefines']==native['predefines'] and len(s['initialEntities'])==10
    assert all(e['active'] is False for e in s['initialEntities'])
    assert [e['registration_key'] for e in s['initialEntities']]==['trap_007_ballis#'+str(i) for i in range(1,11)]
    assert s['parameters']['deploy_capacity']==9 and s['resources']['dp']['initial']==0 and s['resources']['life']['initial']==3
    assert sum(a['count'] for w in s['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn')==73


@pytest.mark.parametrize('mutation',[lambda e:e.update(active=True),lambda e:e.update(active=0),
    lambda e:e.update(registration_key='other'),lambda e:e.update(instanceAlias='other'),lambda e:e['position'].update(row=99)])
def test_hidden_source_cannot_be_authored_active_or_wrong_registration(mutation):
    native,profile,bindings,profiles=fixture();mutation(profile['initial_entities'][0])
    with pytest.raises(ValueError):compose(native,'level_main_05-10',bindings,profiles,predefined_profile=profile)
