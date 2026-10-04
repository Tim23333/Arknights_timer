from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from tools.experiments.chapter05_special_ranged_guard_independent_recheck.test_peer import fixture,L
INPUTS=[];CAPTURES=[]
@pytest.mark.parametrize('free',[False,True])
def test_first_capture_before_blocking_and_control_reconcile_proves_source2_gap(free):
 p=fixture(L,blocked=True)
 if free:p['scenarioDraft']['initialEntities'][1]['components']={'selection_state':{'target_free':True}}
 other=deepcopy(p['scenarioDraft']['initialEntities'][1]);other['instanceAlias']='other';other['position']={'row':2,'col':1};other['components']={'attributes':{'base':{'taunt_level':1000000000,'block_count':0}}};p['scenarioDraft']['initialEntities'].append(other);INPUTS.append(deepcopy(p))
 program=Compiler().compile(p);natural=Engine.create(program,seed=551038);controlled=Engine.create(program,seed=551038)
 assert natural.ctx.spatial.blocked_by('enemy') is None
 controlled.ctx.spatial.blocking();assert controlled.ctx.spatial.blocked_by('enemy')==controlled.session.world.resolve('guard')
 natural.advance(1);controlled.advance(1);caster=next(iter(natural.ctx.get('enemy',('runtime','casts')).values()))
 assert natural.ctx.spatial.blocked_by('enemy')==natural.session.world.resolve('guard') and caster['started_at']==0 and caster['targets']==[natural.session.world.resolve('other')]
 ctrl=controlled.ctx.get('enemy',('runtime','casts'));assert not ctrl if free else next(iter(ctrl.values()))['targets']==[controlled.session.world.resolve('guard')]
 natural.advance(26);controlled.advance(26)
 CAPTURES.append({'free':free,'input':p,'intervention':'One explicit spatial.blocking() before first normal planning; no source values/rules modified','natural_events':thaw(tuple(natural.session.events)),'control_events':thaw(tuple(controlled.session.events)),'natural_snapshot':natural.snapshot(),'control_snapshot':controlled.snapshot()})
 assert [e['payload']['target'] for e in natural.session.events if e['type']=='damage.accepted']==[natural.session.world.resolve('other')]
 assert [e['payload']['target'] for e in controlled.session.events if e['type']=='damage.accepted']==([] if free else [controlled.session.world.resolve('guard')])
