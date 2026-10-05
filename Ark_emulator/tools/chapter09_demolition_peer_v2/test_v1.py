from tools.chapter09_demolition_peer_v2.fixture import *
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=29413907)
def events(s,t):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==t]
def proof(p,name,splits=[28,50],end=80):
 a=create(p);a.advance(end);b=create(p);LOG.mkdir(parents=True,exist_ok=True);pins=[]
 for i,t in enumerate(splits):
  b.advance(t-b.session.time);path=LOG/(name+str(i)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append(pin);b=Engine.restore(b.program,load_bound(path,pin),providers=REG)
 b.advance(end-b.session.time);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'core':CORE,'actual_CPP_head_full_equal':True,'CP_SHAs':pins,'input_digest':digest(p),'events':len(a.session.events)},indent=2),encoding='utf8');return a

@pytest.mark.parametrize('mode,pushed',[('live',False),('remove',True),('expire',True),('inactive',True),('base_immune',True),('buff_immune',True),('inactive_immune',False)])
def test_actual_dynamic_buff_applicability_expiry_immunity_difference_cpp(mode,pushed):
 p=scene(mode);mapping=next(r for r in p['rules'] if r['id']=='rule/'+PREFIX+'push')['parameters']['status_definitions'];assert set(mapping)=={b['id'] for b in p['buffs']};s=create(p);s.advance(28);instances=s.ctx.get('target',('buffs','instances'));assert any(x['definition']==FLAG for x in instances)
 if mode=='expire':
  assert next(x for x in instances if x['definition']==FLAG)['expires_at']==35;s.advance(8);assert not any(x['definition']==FLAG for x in s.ctx.get('target',('buffs','instances')))
 if mode=='inactive':assert next(x for x in instances if x['definition']==FLAG)['applicability']['active'] is False
 if mode=='inactive_immune':assert next(x for x in instances if x['definition']==IMMUNE)['applicability']['active'] is False
 s=proof(p,mode);assert s.ctx.resources.current('target','hp')==HP-2000;assert [t for t,x in events(s,'damage.accepted')]==[44];assert abs(s.ctx.get('target',('spatial','position'))['col']-(3+1.56247 if pushed else 3))<1e-9


def test_missing_runtime_active_Buff_mapping_rejects_and_full_effect_rollback():
 p=scene('live');r=next(x for x in p['rules'] if x['id']=='rule/'+PREFIX+'push');r['parameters']['status_definitions'].pop(FLAG);s=create(p);old=s.session._handlers['domain.ability.effect'];checks=[]
 def handler(session,payload):
  before=session.snapshot();cache=s.ctx.attributes.checkpoint_cache();cursor=s.ctx.last_calculation_event_id
  try:return old(session,payload)
  except (KeyError,ValueError):
   assert session.snapshot()==before;assert s.ctx.attributes.checkpoint_cache()==cache;assert s.ctx.last_calculation_event_id==cursor;checks.append(True);raise
 s.session._handlers['domain.ability.effect']=handler
 with pytest.raises((KeyError,ValueError)):s.advance(45)
 assert checks==[True];assert s.ctx.resources.current('target','hp')==HP;assert s.ctx.get('target',('spatial','position'))=={'row':2,'col':3}


def test_slot_stock_four_attempts_and_current_source_guard():
 p=scene('remove');p['scenarioDraft']['commands']=[{'at':t,'action':'deploy','definition':BODY,'alias':'dev'+str(t),'position':{'row':2,'col':2},'facing':'right'} for t in [9,158,159,309]];s=proof(p,'stock_slot',[80,160],350);assert [t for t,x in events(s,'command.accepted')]==[9,159];assert [t for t,x in events(s,'command.rejected')]==[158,309];assert s.ctx.resources.current('system/battle','dp')==31;assert s.ctx.resources.current('system/battle',STOCK)==0;assert guard()==START


def test_source_definition_conflict_rejected_and_live_source_force_Buff_bound():
 p=scene('remove');p['buffs'].append({'id':FLAG,'kind':'buff','selection_flags':{'abnormal_flags':[7]}});bind_status_definitions(p)
 with pytest.raises(ValueError):Compiler(providers=REG).compile(p)
 p=scene('remove');p['buffs'].append({'id':'buff/peer/source_force','kind':'buff','modifiers':[{'attribute':'base_force_level','layer':'flat','value':1}]});p['scenarioDraft']['scheduledEffects'].append({'at':13,'effect':{'op':'apply_buff','target':3,'buff':'buff/peer/source_force'}});bind_status_definitions(p);s=proof(p,'live_source_force');assert s.ctx.resources.current('target','hp')==HP-2000;assert abs(s.ctx.get('target',('spatial','position'))['col']-(3+1.98705))<1e-9;assert guard()==START
