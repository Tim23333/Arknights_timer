"""Real public singleCold source slows normal and skill native frames through v2."""
import json,hashlib
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.chapter06_units.snmage.test_module_v13_v2 import controlled_package,deploy,sp,flags,damage
from tools.chapter06_units.test_melee_v13_v2 import fixture_package as melee_package,deploy as melee_deploy
from tools.chapter06_units.snmage.build_module import ROOT,COLD,NORMAL,SKILL
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def mage_singlecold(initial=0,old=False):
    p=controlled_package(cold=True);p['entities'][0]['components']['resources']['sp']['initial']=initial
    if old:
        olddata=json.loads((ROOT/'packages/campaign/chapter06_units/snmage/model.json').read_bytes())
        for ability in p['abilities']:
            if ability['id'] in (NORMAL,SKILL):ability['rules'].pop('ability.windup',None)
        p['manifest']=olddata['manifest']
    return p
def melee_singlecold(native,old=False):
    p=melee_package(native,route=True);u=next(u for u in p['entities'] if u.get('metadata',{}).get('native_reference',{}).get('id')==native);u['tags'].append('cold_receiver')
    p['entities'].append({'id':'unit/test/windup/controller','kind':'entity','tags':['test_controller'],'components':{'attributes':{'base':{'max_hp':10}},'resources':{'hp':{'initial':10,'capacity':10,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/ch6/cold/apply5']}})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/test/windup/controller','instanceAlias':'controller','position':{'row':0,'col':4}})
    if old:
        for ability in p['abilities']:ability.get('rules',{}).pop('ability.windup',None)
    return p
def start(p,mage=True):
    s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),seed=6299,providers=providers())
    s.submit({'action':'skill','source':'controller','ability':'ability/ch6/cold/apply5'},at=0)
    (deploy if mage else melee_deploy)(s,at=1)
    return s

@pytest.mark.parametrize('initial,ability',[(0,NORMAL),(2,SKILL)])
def test_actual_mage_singlecold_twenty_over_point7_ceil29_before_real_projectile_hit(initial,ability):
    s=start(mage_singlecold(initial));s.session.advance(34)
    start_event=next(e for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==ability)
    launch=next(e for e in s.session.events if e['type']=='projectile.launched')
    assert launch['time']-start_event['time']==29 and damage(s)==[(33,300)]
    assert s.ctx.attributes.value('mage','attack_speed_ratio')==pytest.approx(.7)
    assert sp(s)==(1 if initial==0 else 0)
    assert (23 in flags(s))==(initial==2)

@pytest.mark.parametrize('native,scaled,outgoing',[('enemy_1006_shield_2',20,500),('enemy_1064_snsbr',18,260)])
def test_actual_melee_singlecold_fourteen_or_twelve_over_point7(native,scaled,outgoing):
    s=start(melee_singlecold(native),False);s.session.advance(35)
    owner=s.session.world.resolve('enemy');began=next(e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==owner)
    packet=next(e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==owner)
    assert packet['time']-began['time']==scaled and packet['payload']['amount']==outgoing
    assert s.ctx.attributes.value('enemy','attack_speed_ratio')==pytest.approx(.7)

@pytest.mark.parametrize('kind',["mage","shield","snsbr"])
def test_actual_singlecold_changed_frame_pending_cast_disk_cp_full_head(kind,tmp_path):
    p=mage_singlecold(2) if kind=='mage' else melee_singlecold('enemy_1006_shield_2' if kind=='shield' else 'enemy_1064_snsbr')
    s=start(p,kind=='mage');s.session.advance(10);cp=tmp_path/(kind+'.json');pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(s.program,load_bound(cp,pin),providers=providers())
    s.session.advance(30);restored.session.advance(30)
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
