import hashlib
import json
from pathlib import Path
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.build_chapter04_volcano_module import build
from tools.build_reference_stage_scenario_v2 import map_plan
from tools.campaign_ordered_checkpoint import write_ordered, load_bound

ROOT = Path(__file__).resolve().parents[3]
INPUTS = []


def actual_eight_fields():
    module = build()
    plan = json.loads((ROOT/'packages/campaign/chapter04_plans/source.plan.json').read_bytes())
    native = plan['stages']['level_main_04-09']['native_document']
    mp = map_plan(native)
    cells = [(i//mp['cols'],i%mp['cols']) for i,t in enumerate(mp['tiles']) if t['tileKey']=='tile_volcano']
    assert len(cells) == 8
    module['entities'] = [{'id':'unit/volcano_probe','kind':'entity','tags':['player'],
        'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':1},
            'attributes':{'base':{'max_hp':10000,'atk':0,'def':9999,'mres':100}},
            'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
            'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
    module['scenarioDraft'] = {'id':'scene/4-9/volcano_field_probe','ruleset':'ruleset/ark_standard',
        'objectives':{},'map':{'rows':mp['rows'],'cols':mp['cols'],'tiles':mp['tiles'],
        'tile_mechanics':module['manifest']['metadata']['tile_profiles']},
        'initialEntities':[{'definition':'unit/volcano_probe','instanceAlias':f'probe/{i}',
            'position':{'row':r,'col':c}} for i,(r,c) in enumerate(cells)]}
    return module,cells


def test_actual_eight_native_cells_bound_700_and_sampled_13_19_ordered_resume(tmp_path):
    p,cells = actual_eight_fields(); INPUTS.append(p)
    s = Engine.create(Compiler().compile(p),seed=73904)
    fields = s.ctx.periodic_fields.state()['fields']
    assert [f['cell'] for f in fields.values()] == [{'row':r,'col':c} for r,c in cells]
    assert all(f['blackboard']=={'damage':700.0,'cd_min':13.0,'cd_max':19.0} for f in fields.values())
    cp = tmp_path/'fields.ordered.json'; pin = write_ordered(cp,s.checkpoint())
    restored = Engine.restore(s.program,load_bound(cp,pin)); s.advance(600); restored.advance(600)
    triggers = [e for e in s.session.events if e['type']=='field.triggered']
    hits = [e for e in s.session.events if e['type']=='damage.accepted']
    assert len(triggers)==len(hits)==8 and len({e['payload']['field_uid'] for e in triggers})==8
    assert all(390<=e['time']<570 for e in triggers)
    assert all(e['payload']['amount']==700.0 and e['payload']['source'] is None for e in hits)
    assert all(s.ctx.resources.current(f'probe/{i}','hp')==9300 for i in range(8))
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_actual_uniform_calculations_consume_named_samples_and_bound_formula():
    p,_ = actual_eight_fields(); INPUTS.append(p)
    s = Engine.create(Compiler().compile(p),seed=73904); s.advance(600)
    calculations = [e for e in s.session.events if e['type']=='calculation'
        and e['payload'].get('calculation_id')=='field.trigger']
    assert len(calculations)==16
    for event in calculations:
        payload=thaw(event['payload']); inputs=payload['trace']['inputs']
        expected=13.0+6.0*inputs['samples'][0]['value']
        assert payload['value']['next_delay_seconds']==expected
    assert hashlib.sha256((ROOT/'packages/campaign/chapter04_environment/source.reference.json').read_bytes()).hexdigest()=='148a5a8648801f8c7eee655d5c0daa1f4f7469cefe3abd2d304dcdc33a121dc8'
