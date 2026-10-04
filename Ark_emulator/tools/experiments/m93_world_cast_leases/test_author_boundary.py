import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
def fixture():
 r=json.loads((ROOT/'validation/campaign/m78_independent_controller_peer_v3/verification.json').read_bytes())
 return next(p for p in r['actual_inputs'] if any(a['id']=='ability/peer/external' for a in p['abilities']))
def create(p):INPUTS.append(p);return Engine.create(Compiler().compile(p),seed=93078)
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def test_same_source_distinct_cast_rejected_with_all_refresh_writes_rolled_back():
 p=fixture();buff=p['definitions'][0]['target_buff'];source=p['entities'][0]
 for key in ['first','second']:
  aid='ability/author/'+key;p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual','parameters':{'blocks_attacks':False},'on_start':[{'op':'apply_buff','target':3,'buff':buff,'bind_to_cast':True}]},'timeline':[{'at':1000,'effect':{'op':'heal','scale':0}}]});source['components']['abilities'].append(aid)
 s=create(p);s.ctx.abilities.start('caster','ability/author/first');before=s.checkpoint()
 with pytest.raises(ValueError,match='cannot be shared'):s.ctx.abilities.start('caster','ability/author/second')
 assert s.checkpoint()==before;capture(s,'same_source_other_cast')
def test_lazy_expired_uid_is_removed_normally_and_stale_row_does_not_lock_new_uid():
 p=fixture();buff=p['definitions'][0]['target_buff'];next(b for b in p['buffs'] if b['id']==buff)['duration_seconds']=1/30
 s=create(p);s.ctx.abilities.start('other','ability/peer/external');external=next(iter(s.ctx.get('other',('runtime','casts')).values()));old_uid=external['owned_buffs'][0]['instance']
 normal=next(a['id'] for a in p['abilities'] if a['id'].endswith('/normal'));s.ctx.abilities.start('caster',normal,automatic=True);own=next(iter(s.ctx.get('caster',('runtime','casts')).values()))
 s.advance(1);assert s.session.time==1 and s.ctx.get('victim',('buffs','instances'))[0]['expires_at']==1
 uid=s.ctx.abilities.apply_cast_buff('caster',own['id'],'victim',buff)
 assert uid!=old_uid;assert s.ctx.get('other',('runtime','casts',external['id'],'owned_buffs'))==external['owned_buffs']
 removed=[e for e in s.session.events if e['type']=='buff.removed'];assert removed and any(e['payload']['instance']==old_uid for e in removed)
 capture(s,'lazy_expired_uid_normal_log')
def test_canceled_holder_releases_and_can_reacquire_without_editing_history():
 p=fixture();s=create(p);buff=p['definitions'][0]['target_buff'];s.ctx.abilities.start('other','ability/peer/external');old=tuple(s.session.events)
 s.ctx.abilities.interrupt('other','author_cancel');assert tuple(s.session.events)[:len(old)]==old
 assert s.ctx.get('other',('runtime','casts'))=={} and s.ctx.get('victim',('buffs','instances'))==[]
 normal=next(a['id'] for a in p['abilities'] if a['id'].endswith('/normal'));s.ctx.abilities.start('caster',normal,automatic=True);own=next(iter(s.ctx.get('caster',('runtime','casts')).values()))
 uid=s.ctx.abilities.apply_cast_buff('caster',own['id'],'victim',buff);assert uid;capture(s,'canceled_holder_reacquire')
@pytest.mark.parametrize('instance',['missing','buff/3/999'])
def test_direct_bind_missing_uid_rejected_without_writes(instance):
 p=fixture();s=create(p);s.ctx.abilities.start('other','ability/peer/external');cast=next(iter(s.ctx.get('other',('runtime','casts')).values()));before=s.checkpoint()
 with pytest.raises(ValueError,match='live target instance'):s.ctx.abilities.bind_buff('other',cast['id'],'victim',instance)
 assert s.checkpoint()==before;capture(s,'invalid_uid_'+instance)
