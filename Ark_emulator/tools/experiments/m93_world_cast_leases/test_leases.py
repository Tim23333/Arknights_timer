import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
ROOT=Path(__file__).resolve().parents[3]
INPUTS=[];CAPTURES=[]
def make(shared=True):
 r=json.loads((ROOT/'validation/campaign/m78_independent_controller_peer_v3/verification.json').read_bytes())
 p=next(p for p in r['actual_inputs'] if any(a['id']=='ability/peer/external' for a in p['abilities']))
 buff=p['definitions'][0]['target_buff'];b=next(b for b in p['buffs'] if b['id']==buff)
 if not shared:b['stacking']['identity']=['definition','source','target']
 INPUTS.append(p);return Engine.create(Compiler().compile(p),seed=780403),buff
def stores(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'random':s.session.random.snapshot(),'events':s.session._events.snapshot()}
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def test_attachment_conflict_restores_generation_source_controls_rng_tasks_events():
 s,buff=make();s.submit({'action':'skill','source':'other','ability':'ability/peer/external'},at=28)
 before=[];original=s.ctx.attachments.step
 def boundary(session,payload):before.append(stores(s));return original(session,payload)
 s.session._handlers['domain.attachment.step']=boundary
 with pytest.raises(ValueError,match='cannot be shared'):s.advance(30)
 assert stores(s)==before[-1];row=s.ctx.get('victim',('buffs','instances'))[0]
 assert row['source']==s.session.world.resolve('other') and row['generation']==1
 assert next(iter(s.ctx.get('other',('runtime','casts')).values()))['owned_buffs']==[{'target':3,'instance':row['id']}]
 capture(s,'attachment_conflict_full_rollback')
def test_bound_effect_conflict_random_refresh_effects_are_atomic():
 s,buff=make();s.advance(5)
 # Interrupt the original source before arrival; another long-lived public cast
 # can own the generic target lease without the attachment acquiring it.
 s.ctx.abilities.interrupt('caster','author_setup')
 s.ctx.abilities.start('other','ability/peer/external');old=next(iter(s.ctx.get('other',('runtime','casts')).values()))
 s.ctx.abilities.start('caster',next(a['id'] for a in s.program.definitions.values() if a.get('kind')=='ability' and a['id'].endswith('/normal')),automatic=True)
 own=next(iter(s.ctx.get('caster',('runtime','casts')).values()));before=stores(s)
 with pytest.raises(ValueError,match='cannot be shared'):
  s.ctx.effects.execute('caster',['victim'],{'op':'random','stream':'author_lease_conflict','on_success':[{'op':'apply_buff','buff':buff,'bind_to_cast':True}]},cast=own)
 assert stores(s)==before;assert s.ctx.get('victim',('buffs','instances'))[0]['source']==s.session.world.resolve('other');capture(s,'effect_conflict_atomic')
def test_same_source_same_cast_rebinding_is_exactly_idempotent():
 s,buff=make(False);s.advance(30);cast=next(iter(s.ctx.get('caster',('runtime','casts')).values()));lease=cast['owned_buffs'][-1];before=s.checkpoint()
 s.ctx.abilities.bind_buff('caster',cast['id'],lease['target'],lease['instance']);s.ctx.abilities.bind_buff(s.session.world.resolve('caster'),cast['id'],'victim',lease['instance'])
 assert s.checkpoint()==before;capture(s,'idempotent_bind')
def test_external_default_identity_survives_caster_retirement():
 s,buff=make(False);s.submit({'action':'skill','source':'other','ability':'ability/peer/external'},at=28);s.advance(31)
 rows=s.ctx.get('victim',('buffs','instances'));assert len(rows)==2
 ext=next(b for b in rows if b['source']==s.session.world.resolve('other'))
 s.ctx.lifecycle.retire('caster','withdrawn');rows=s.ctx.get('victim',('buffs','instances'))
 assert len(rows)==1 and rows[0]==ext;capture(s,'external_owner_survives')
def test_retired_holder_releases_uid_and_new_source_can_acquire():
 s,buff=make();s.ctx.abilities.interrupt('caster','setup');s.ctx.abilities.start('other','ability/peer/external');s.ctx.lifecycle.retire('other','withdrawn')
 assert not s.ctx.get('victim',('buffs','instances'))
 s.ctx.abilities.start('caster',next(a['id'] for a in s.program.definitions.values() if a.get('kind')=='ability' and a['id'].endswith('/normal')),automatic=True)
 cast=next(iter(s.ctx.get('caster',('runtime','casts')).values()));uid=s.ctx.abilities.apply_cast_buff('caster',cast['id'],'victim',buff)
 assert uid and s.ctx.get('victim',('buffs','instances'))[0]['source']==s.session.world.resolve('caster');capture(s,'retired_holder_reacquire')
