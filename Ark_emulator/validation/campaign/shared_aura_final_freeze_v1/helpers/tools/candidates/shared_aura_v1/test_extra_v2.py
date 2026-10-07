"""Source range departure, terminal waiting cancellation and callback lease boundaries."""
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_shared_aura_v8_candidate'));sys.path.insert(1,str(ROOT))
from tools.candidates.shared_aura_v1.test_shared_guarded_v9 import package,waiting_package,children,MARKER
from ark_sim import Compiler,Engine
def test_one_parent_real_range_departure_releases_only_its_lease():
 p=package();p['scenarioDraft']['map']={'rows':1,'cols':8};p['selectors'][0]['region']={'type':'radius','radius':3};p['selectors'].append({'id':'selector/peer/p1','kind':'selector','region':{'type':'all'},'filters':[{'tag':'parent1'}]});p['scenarioDraft']['scheduledEffects']=[{'at':5,'effect':{'op':'move','selector':'selector/peer/p1','position':{'row':0,'col':7}}}];s=Engine.create(Compiler().compile(p));ids=[i['id'] for i in children(s)];s.session.advance(7);assert [i['id'] for i in children(s)]==ids and all(len(i['aura_leases'])==1 and i['source']==s.session.world.resolve('parent2') for i in children(s));assert s.ctx.attributes.value('receiver','atk')==120
def test_terminal_or_cancelled_waiting_cannot_keep_aura():
 s=Engine.create(Compiler().compile(waiting_package()));s.ctx.effects.execute('parent2',[s.session.world.resolve('parent1')],{'op':'damage','damage_type':'true','scale':0,'additions':100});assert children(s);s.ctx.rebirth.cancel(s.session.world.resolve('parent1'),'test_cancelled');s.ctx.buffs.reconcile();assert not children(s) and not s.ctx.rebirth._aura_waiting_begins
def test_child_on_apply_removes_other_parent_without_ghost_second_lease():
 p=package();p['selectors'].append({'id':'selector/peer/kill_p2','kind':'selector','region':{'type':'all'},'filters':[{'tag':'parent2'}]});p['buffs'][0]['effects']=[{'op':'retire','selector':'selector/peer/kill_p2','parameters':{'reason':'withdrawn'}}];s=Engine.create(Compiler().compile(p));assert not s.ctx.alive('parent2') and all(len(i['aura_leases'])==1 and i['source']==s.session.world.resolve('parent1') for i in children(s));assert s.ctx.attributes.value('receiver','atk')==120
def test_last_release_on_remove_retires_other_parent_does_not_restore_maps():
 p=package();p['buffs'][0]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}];s=Engine.create(Compiler().compile(p));s.ctx.lifecycle.retire('parent1','withdrawn');assert children(s);s.ctx.lifecycle.retire('parent2','withdrawn');assert not children(s) and not any(i.get('aura_members') for uid in ('parent1','parent2') for i in s.ctx.entity(uid)['components']['buffs']['instances'])
