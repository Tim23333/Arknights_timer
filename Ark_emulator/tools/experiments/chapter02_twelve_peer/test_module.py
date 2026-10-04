import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
P=ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.reference_module.json'
def module():return json.loads(P.read_bytes())
def binding(p,name):return next(r for r in p['manifest']['metadata']['variant_bindings'] if r['variant_id'].split('@')[0]==name)
def defn(p,uid):return next(x for x in p['definitions'] if x['id']==uid)

def test_all_twelve_actual_life_loss_is_distinct_from_entity_leak_count():
    p=module();rows=p['manifest']['metadata']['variant_bindings'];assert len(rows)==12
    for row in rows:
        q=deepcopy(p);uid=row['unit_definition'];unit=defn(q,uid);native_loss=unit['components']['lifecycle']['leak_loss']
        q['scenarioDraft']={'id':'scene/peer/leak','ruleset':'ruleset/ark_standard','objectives':{'life_resource':'lives'},'resources':{'lives':{'initial':99999,'capacity':99999}},
            'map':{'rows':1,'cols':1},'initialEntities':[{'definition':uid,'instanceAlias':'enemy','position':{'row':0,'col':0},
                'route':{'motionMode':row['native_motion'],'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':0},'checkpoints':[]}}]}
        s=Engine.create(Compiler().compile(q),seed=4818);s.advance(2)
        assert s.ctx.state()['leaks']==1 and s.ctx.state()['kills']==0 and s.ctx.resources.current('system/battle','lives')==99999-native_loss
        assert native_loss==(2 if row['variant_id'].startswith('enemy_1500_skulsr@') else 1)

def block_scene(name):
    p=module();enemy=binding(p,name)['unit_definition']
    blocker={'id':'unit/peer/blocker','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':4000,'def':10,'mres':20,'block_count':1,'taunt_level':0}},
        'resources':{'hp':{'initial':4000,'capacity':4000,'role':'health'}},'deployable':{'base_cost':1,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}}}
    other=deepcopy(blocker);other['id']='unit/peer/high_taunt';other['components'].pop('deployable');other['components']['attributes']['base'].update(block_count=0,taunt_level=20)
    p['definitions'] += [blocker,other,{'id':'buff/peer/hold','kind':'buff','duration_seconds':1/30,'control':{'attack':False}}]
    p['scenarioDraft']={'id':'scene/peer/input_target','ruleset':'ruleset/ark_standard','objectives':{},'roster':['unit/peer/blocker'],
        'resources':{'dp':{'initial':100,'capacity':100}},'map':{'rows':5,'cols':8},'initialEntities':[
            {'definition':enemy,'instanceAlias':'enemy','position':{'row':2,'col':2},'components':{'buffs':{'initial':['buff/peer/hold']}},
                'route':{'motionMode':0,'startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':7},'checkpoints':[]}},
            {'definition':'unit/peer/high_taunt','instanceAlias':'other','position':{'row':2,'col':3}}]}
    return p

@pytest.mark.parametrize('name',['enemy_1011_wizard','enemy_1028_mocock'])
def test_exact_input_target_combat_cannot_be_overridden_by_arbitrary_high_taunt(name):
    p=block_scene(name);s=Engine.create(Compiler().compile(p),seed=4819);s.submit({'action':'deploy','entity':'unit/peer/blocker','position':{'row':2,'col':2},'alias':'blocker'},at=0);s.advance(1)
    assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('blocker')
    s.advance(40);packets=[e for e in s.session.events if e['type']=='damage.accepted']
    assert packets and all(e['payload']['target']==s.session.world.resolve('blocker') for e in packets)
    assert s.ctx.resources.current('other','hp')==4000
