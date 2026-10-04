from tools.chapter08_bsnake_combat.test_source_v3 import package,make,proof,hits
import pytest
@pytest.mark.parametrize('speed,hit,finish',[(1,31,70),(2,16,35)])
def test_native70full_busy_scaledASPD_without_extending_31hit(speed,hit,finish):
 p=package()
 if speed==2:
  p['buffs'].append({'id':'buff/test/busyASPD','kind':'buff','modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':1}]});p['entities'][0]['components']['buffs']['initial'].append('buff/test/busyASPD')
 pr,s,reg=make(p);s.advance(hit+1);assert len(s.ctx.get('boss',('runtime','casts')))==1;assert [(e['time'],e['payload']['amount']) for e in hits(s,'ability/ch8/bsnake/normal/phase0')]==[(hit,770)];s.advance(finish-hit-2);assert len(s.ctx.get('boss',('runtime','casts')))==1;s.advance(2);assert not s.ctx.get('boss',('runtime','casts'));assert [(e['time']) for e in s.session.events if e['type']=='ability.finished' and e['payload']['ability']=='ability/ch8/bsnake/normal/phase0']==[finish]
