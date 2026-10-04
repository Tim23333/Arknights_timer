"""Preserved required singleCold failures in original source content timing."""
import pytest,json,hashlib
from pathlib import Path
from tools.chapter06_units.test_windup_v2 import mage_singlecold,melee_singlecold,start
from tools.chapter06_units.snmage.build_module import ROOT,NORMAL,SKILL

@pytest.mark.parametrize('name,expected', [('mage_normal',29),('mage_skill',29),('shield',20),('snsbr',18)])
def test_required_original_native_affectedBySlowDown_consumes_effective_point7(name,expected):
    mage=name.startswith('mage')
    p=mage_singlecold(2 if name=='mage_skill' else 0,old=True) if mage else melee_singlecold('enemy_1006_shield_2' if name=='shield' else 'enemy_1064_snsbr',old=True)
    s=start(p,mage);s.session.advance(40);source=s.session.world.resolve('mage' if mage else 'enemy')
    began=next(e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==source)
    event=next(e for e in s.session.events if e['type']==('projectile.launched' if mage else 'damage.accepted') and e['payload']['source']==source)
    actual=event['time']-began['time'];out=ROOT/'packages/campaign/chapter06_units/windup_old_failures';out.mkdir(parents=True,exist_ok=True)
    (out/(name+'.actual.json')).write_bytes((json.dumps({'schema':'ark-sim/ch6-required-old-source-windup-failure/v1','name':name,'source_attack_speed_ratio':s.ctx.attributes.value('mage' if mage else 'enemy','attack_speed_ratio'),'cast_started':began['time'],'payload_time':event['time'],'actual_relative_frame':actual,'expected_relative_frame':expected,'required_consumer_passed':actual==expected,'source_flags':{'affectedBySlowDown':1,'timeMode':0},'old_module_sha256':hashlib.sha256((ROOT/'packages/campaign/chapter06_units'/('snmage/model.json' if mage else 'melee.model.json')).read_bytes()).hexdigest(),'source_method_body_verified':False,'reference_replaceable_min_speed':.01,'whole_stage_executed':False,'client_verified':False},indent=2)+'\n').encode('utf8'))
    assert actual==expected,'Original unscaled source windup does not consume effective ASPD.7'
