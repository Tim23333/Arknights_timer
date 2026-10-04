from copy import deepcopy
import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[1]


def test_actual_mortar_hit_ignores17_but_requires9_immunity(tmp_path):
    p=json.loads((ROOT/'packages/campaign/chapter03_models/mortar.reference.json').read_bytes())
    visibility=json.loads((ROOT/'packages/campaign/chapter03_visibility/lurker_sensor.model.json').read_bytes())
    available=deepcopy(next(r for r in visibility['rules'] if r.get('contract')=='targeting.availability'));p['rules'].append(available)
    state={'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],
        'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],'target_free':False,'ally_target_free':False,
        'heal_free':False,'camouflage':False,'can_select_camouflage':False}
    target={'id':'unit/test_victim','kind':'entity','tags':['player'],'rules':{'targeting.availability':available['id']},'components':{
        'spatial':{},'selection_state':state,'attributes':{'base':{'max_hp':10000,'def':50,'mres':0}},
        'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'abilities':['ability/immune']}}
    p['entities'].append(target)
    p['buffs']=[{'id':'buff/immune9','kind':'buff','selection_flags':{'abnormal_immunes':[9]}},
        {'id':'buff/free','kind':'buff','selection_flags':{'target_free':True}}]
    p['abilities'].append({'id':'ability/immune','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/immune9'}]},'timeline':[]})
    source=p['entities'][0]['id']
    p['scenarioDraft']={'id':'scene/test/mortar_visibility_combo','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':7,'cols':8},
        'initialEntities':[{'definition':source,'instanceAlias':'mortar','position':{'row':3,'col':0}},
        {'definition':target['id'],'instanceAlias':'main','position':{'row':3,'col':2}},
        {'definition':target['id'],'instanceAlias':'hidden','position':{'row':4,'col':2},'components':{'selection_state':{'motion':2,'abnormal_flags':[9],'camouflage':True}}},
        {'definition':target['id'],'instanceAlias':'camo','position':{'row':2,'col':2},'components':{'selection_state':{'motion':2,'abnormal_flags':[17],'camouflage':True}}},
        {'definition':target['id'],'instanceAlias':'free','position':{'row':3,'col':3},'components':{'buffs':{'initial':['buff/free']}}}]}
    s=Engine.create(Compiler().compile(p),seed=5409);s.advance(40)
    assert s.ctx.resources.current('main','hp')==9650
    assert s.ctx.resources.current('camo','hp')==9650
    assert s.ctx.resources.current('hidden','hp')==10000 and s.ctx.resources.current('free','hp')==10000
    s.submit({'action':'skill','source':'hidden','ability':'ability/immune'},at=40)
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.advance(140);r.advance(140)
    assert s.ctx.resources.current('hidden','hp')==9650 and s.ctx.resources.current('free','hp')==10000
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
