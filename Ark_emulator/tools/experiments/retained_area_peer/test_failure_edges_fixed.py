import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from copy import deepcopy
from tools.experiments.retained_area_peer.test_peer_fixed import fixture,make,fire,capture,INPUTS
def test_area_failure_rolls_back_new_random_stream_and_scheduled_effect_job():
 p,area,_=fixture();area['effects'].insert(1,{'op':'random','stream':'area_peer_noise','probability':1,'on_success':[{'op':'schedule','delay_seconds':.1,'effect':{'op':'emit','event':'peer.scheduled_should_rollback'}}]})
 p['rules'][0]['implementation']['expression']="{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/launched','duration_seconds':True}]}";s=make(p);fire(s);s.advance(6);before_rng=s.session.random.snapshot();before_id=s.session.scheduler.next_task_id
 with pytest.raises(ValueError):s.advance(1)
 capture(s,'area_random_job_fault');assert s.session.random.snapshot()==before_rng and s.session.scheduler.next_task_id==before_id
 assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.effect'] and not s.ctx.projectiles._area_payload_scopes and not s.ctx.projectiles._impact_payload_scopes and not s.ctx.projectiles._inflight_hits
@pytest.mark.parametrize('members',[[3,3,5],[True,5]])
def test_invalid_area_member_ids_never_acquire_payload_scope(members):
 p,area,_=fixture();area.pop('radius');area['membership_rule']='rule/peer/bad_members';p['rules'].append({'id':'rule/peer/bad_members','kind':'rule','contract':'area.members','implementation':{'type':'provider','provider':'peer.bad_members'}})
 def bad(inputs,params,context):return members
 bad.version='peer-area-members-validation/v1';registry={**BUILTIN_PROVIDERS,'peer.bad_members':bad};INPUTS.append(deepcopy(p));s=Engine.create(Compiler(providers=registry).compile(p),seed=62161,providers=registry);fire(s)
 with pytest.raises(ValueError):s.advance(10)
 capture(s,'bad_members_'+repr(members));assert not s.ctx.projectiles._area_payload_scopes and not s.ctx.projectiles._impact_payload_scopes and not s.ctx.projectiles._inflight_hits
