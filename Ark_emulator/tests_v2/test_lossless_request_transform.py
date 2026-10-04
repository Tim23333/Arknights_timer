import json
from pathlib import Path

import pytest

from ark_sim import Compiler,Engine
from ark_sim.contracts import freeze,thaw
from ark_sim.domains.request_transforms import request_field_transform
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

ROOT=Path(__file__).resolve().parents[1]


def test_pure_transform_preserves_every_other_typed_field_and_input_immutability():
    request={'op':'damage','damage_type':'true','scale':2,'distance':.5,'parameters':{'value':1200,'nested':[False,1,1.0,-0.0]},
        'rules':{'damage.pipeline':'rule/custom'},'custom_extension':{'keep':'all'}}
    locked=freeze(request)
    result=request_field_transform({'effect':locked},{'field':'scale','factor':1.7,'default':1},{})
    assert result['effect']['scale']==3.4
    for key,value in request.items():
        if key!='scale':assert result['effect'][key]==value
    assert thaw(locked)==request
    result['effect']['parameters']['nested'].append(3)
    assert len(locked['parameters']['nested'])==4


@pytest.mark.parametrize('operand',[True,'1',None,float('inf'),float('nan')])
def test_non_numeric_and_non_finite_operands_rejected(operand):
    with pytest.raises(ValueError,match='finite numeric'):
        request_field_transform({'effect':{'scale':operand}},{'field':'scale','factor':1.7,'default':1},{})


def test_missing_field_uses_explicit_default_and_overflow_rejects():
    assert request_field_transform({'effect':{'distance':.5}},{'field':'scale','factor':1.7,'default':1},{})['effect']=={'distance':.5,'scale':1.7}
    with pytest.raises(ValueError,match='result must be finite'):
        request_field_transform({'effect':{'scale':1e308}},{'field':'scale','factor':1e308,'default':1},{})


def fixture():
    from test_chapter02_reference_tile_fields import fixture as fields_fixture
    from tools.build_chapter02_tile_request_models import build
    p=fields_fixture('tile_gazebo');new=build()
    p['rules']=[r for r in p['rules'] if r['id']!='rule/ch2/gazebo_flying_scale']
    p['rules'].append(next(r for r in new['buffs.lossless_request.model.json']['rules'] if r['id']=='rule/ch2/gazebo_flying_scale'))
    weedy=json.loads((ROOT/'packages/campaign/skills.weedy.json').read_bytes())
    rule=next(r for r in weedy['rules'] if r['id']=='rule/campaign_weedy_distance_damage');p['rules'].append(rule)
    p['entities'][-1]['components']['abilities'].append('ability/test_distance_hit')
    p['entities'].append({'id':'unit/test_fly','kind':'entity','tags':['enemy','test_fly'],
        'components':{'spatial':{},'selection_state':{'side':1,'motion':2},
            'attributes':{'base':{'max_hp':5000,'def':50,'mres':20}},
            'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}}}})
    p['selectors'].append({'id':'selector/test_fly','kind':'selector','region':{'type':'all'},'filters':[{'tag':'test_fly'},{'state':'alive'}]})
    p['abilities'].append({'id':'ability/test_distance_hit','kind':'ability','selector':'selector/test_fly',
        'activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'true','distance':.5,
            'parameters':{'value':1200,'per_distance':1},'rules':{'damage.pipeline':rule['id']}}]},'timeline':[]})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/test_fly','instanceAlias':'fly','position':{'row':0,'col':2}})
    return p


def test_actual_selected_weedy_rule_composes_and_saved_replay_keeps_all_events(tmp_path):
    s=Engine.create(Compiler().compile(fixture()),seed=4301)
    s.submit({'action':'skill','source':'target','ability':'ability/test_enter'},at=0)
    s.submit({'action':'skill','source':'target','ability':'ability/test_distance_hit'},at=1)
    s.advance(1);cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
    s.advance(2);r.advance(2)
    assert s.ctx.resources.current('fly','hp')==4400
    assert not any(e['type']=='command.rejected' for e in s.session.events)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
