from copy import deepcopy
import pytest
from tools.experiments.chapter06_buff_joint_peer.test_peer import fixture,make,buffs,capture,exact
def test_unoverridden_permanent_definition_still_has_no_expiry():
 p,e=fixture("{'accepted':False,'operations':[]}",permanent=True);s=make(p);s.ctx.buffs.apply('source','victim','buff/peer/b');assert buffs(s)[0]['expires_at'] is None;s.advance(12);assert buffs(s)[0]['expires_at'] is None;capture(s,'legacy_permanent')
def test_explicit_zero_application_contributes_no_attributes_control_or_immediate_effects():
 p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/b','duration_seconds':0}]}",permanent=True)
 p['buffs'][1]['control']={'attack':False};p['buffs'][1]['effects']=[{'op':'modify_resource','resource':'hp','delta':-25}]
 s=make(p);s.ctx.effects.execute('source',['victim'],{k:v for k,v in e.items() if k!='target'});capture(s,'zero_immediate_effect')
 assert s.ctx.resources.current('victim','hp')==1000
 s.advance(0);assert not buffs(s) and not s.ctx.get('victim',('attributes','modifiers'),[]) and s.ctx.buffs.controls('victim')['attack']
def test_zero_periodic_interval_is_not_scheduled_or_dealt_after_immediate_expiry():
 p,e=fixture("{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/b','duration_seconds':0}]}",permanent=True)
 p['buffs'][1]['interval_seconds']=.1;p['buffs'][1]['effects']=[{'op':'modify_resource','resource':'hp','delta':-25}]
 s=make(p);s.ctx.effects.execute('source',['victim'],{k:v for k,v in e.items() if k!='target'});s.advance(6);capture(s,'zero_periodic')
 assert s.ctx.resources.current('victim','hp')==1000 and not buffs(s)
def test_valid_but_unhashable_foreign_remove_uid_is_rejected_as_valueerror_and_public_result():
 p,e=fixture("{'accepted':True,'operations':[{'kind':'remove','buff':'buff/peer/a','instance':[],'generation':1}]}");s=make(p);before=s.session.world.snapshot()
 s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=0)
 s.advance(1);capture(s,'unhashable_remove_uid')
 assert s.session.world.snapshot()==before and [e['type'] for e in s.session.events if e['type'].startswith('command.')]==['command.rejected']
