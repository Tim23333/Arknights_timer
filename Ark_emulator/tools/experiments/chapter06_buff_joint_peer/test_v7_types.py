import pytest
from ark_sim import Compiler
from tools.experiments.chapter06_buff_joint_peer.test_peer import fixture,make,capture,INPUTS
@pytest.mark.parametrize('allowed',[[{}],[[]],[True],['buff/peer/a',{}],['buff/peer/a','buff/peer/a'],[],['buff/peer/a']*33])
def test_noop_bad_allowed_types_reject_as_content_valueerror(allowed):
 p,e=fixture("{'accepted':False,'operations':[]}");p['abilities'][0]['activation']['on_start'][0]['allowed']=allowed;INPUTS.append(p)
 with pytest.raises(ValueError):Compiler().compile(p)
@pytest.mark.parametrize('uid',[{},None,True,1,''])
def test_remove_bad_uid_becomes_public_rejection_without_world_mutation(uid):
 p,e=fixture(repr({'accepted':True,'operations':[{'kind':'remove','buff':'buff/peer/a','instance':uid,'generation':1}]}));s=make(p);before=s.session.world.snapshot();s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=0);s.advance(1);capture(s,'bad_uid_'+repr(uid))
 assert before==s.session.world.snapshot() and len([e for e in s.session.events if e['type']=='command.rejected'])==1
def test_invalid_late_operation_cannot_remove_earlier_owned_buff_or_call_on_remove():
 p,e=fixture("{'accepted':True,'operations':[{'kind':'remove','buff':'buff/peer/a','instance':'buff/3/1','generation':1},{'kind':'apply','buff':'buff/peer/b','duration_seconds':True}]}",callback=2);s=make(p);s.ctx.buffs.apply('source','victim','buff/peer/a');before=s.session.world.snapshot();s.submit({'action':'skill','source':'source','ability':'ability/peer/application'},at=0);s.advance(1);capture(s,'late_invalid_operation')
 assert s.session.world.snapshot()==before and s.ctx.active('source') and len([e for e in s.session.events if e['type']=='command.rejected'])==1
