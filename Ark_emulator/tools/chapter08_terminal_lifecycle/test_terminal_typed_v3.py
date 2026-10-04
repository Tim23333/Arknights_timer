import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_terminal_lifecycle_v3_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim.domains.terminal_lifecycle import buff_bound,cast_valid
from tools.chapter08_terminal_lifecycle.test_terminal_completion_v5 import make,BUFF
import pytest
@pytest.mark.parametrize('field',['generation','source','target'])
def test_Bool_registry_fields_cannot_equal_integer_identity(field):
 pr,s,reg,p=make();s.advance(320);ref=s.session.world.resolve('boss');rows=s.ctx.get(ref,('buffs','instances'));inst=next(i for i in rows if i['definition']==BUFF);assert buff_bound(s.ctx,ref,inst)
 state=s.ctx.get(ref,('runtime','rebirth'));state['terminal']['buff_leases'][inst['id']][field]=True;s.ctx.set(ref,('runtime','rebirth'),state);assert not buff_bound(s.ctx,ref,inst);s.advance(80);assert s.ctx.alive('boss') and not [e for e in s.session.events if e['type']=='entity.terminal.completed']

def test_retired_source_does_not_keep_real_finish_buff_authority():
 pr,s,reg,p=make();s.advance(320);s.ctx.lifecycle.retire('boss','withdrawn');s.advance(80);assert not [e for e in s.session.events if e['type']=='entity.terminal.completed'];assert not getattr(s.ctx.rebirth,'_terminal_removing',[])

def test_callback_on_remove_cannot_grant_undeclared_ordinary_cast():
 pr,s,reg,p=make();s.advance(320);before=s.checkpoint()
 from ark_sim.domains.terminal_lifecycle import authorize
 with pytest.raises(ValueError):authorize(s.ctx,s.session.world.resolve('boss'),'ability/ch8/bsnake/firecommon',True)
 assert s.checkpoint()==before
