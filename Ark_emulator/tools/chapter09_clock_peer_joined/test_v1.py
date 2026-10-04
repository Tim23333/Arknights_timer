from tools.chapter09_clock_peer_joined.fixture import *
from ark_sim.contracts import digest,thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest,json

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=71125)
def events(s,kind):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==kind]
def proof(p,name,split,end):
 a=create(p);a.advance(split);LOG.mkdir(parents=True,exist_ok=True);f=LOG/(name+'.checkpoint.json');pin=write_ordered(f,a.checkpoint());b=Engine.restore(a.program,load_bound(f,pin),providers=REG);a.advance(end-split);b.advance(end-split);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot()
 REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'runtime':CORE,'actual_CPP_head_full_equal':True,'events':len(a.session.events),'input_digest':digest(p),'CP_SHA':pin},indent=2),encoding='utf8');return a
@pytest.mark.parametrize('override,ready',[(False,64),(True,82)])
def test_controlled_ability_local_custom_recovery_and_effect_scope_override(override,ready):
 s=proof(clock_scene(effect_override=override),'clock_scope_'+str(override),7,10);assert not events(s,'command.rejected');assert s.ctx.get('worker',('runtime','cooldowns','ability/peer/work'))==ready;updates=[p for _,p in events(s,'ability.cooldown.updated') if p['ability']=='ability/peer/work'];assert len(updates)==1;assert updates[0]['ready_at']==ready;assert updates[0]['duration_seconds']==(2.5 if override else 1.875)

def test_external_accepted_interrupt_cancels_exact_owned_ability_tasks():
 p=clock_scene();p['scenarioDraft']['commands']=[{'at':0,'action':'skill','source':'worker','ability':'ability/peer/work'},{'at':7,'action':'skill','source':'director','ability':'ability/peer/stop_work'}];s=proof(p,'owned_interrupt',6,65);assert not events(s,'command.rejected');assert s.ctx.get('worker',('runtime','casts'))=={};assert not events(s,'peer.work.hit');assert any(x['ability']=='ability/peer/work' for _,x in events(s,'ability.interrupted'));assert not any(t['kind'].startswith('domain.ability') for t in s.session.scheduler.pending)
 traces=[x['trace']['context'] for _,x in events(s,'calculation') if x.get('calculation_id')=='ability.recovery'];assert any(c.get('source_id')==s.session.world.resolve('worker') and c.get('owner_id') is None and c.get('target_id') is None for c in traces)


def test_self_lifecycle_relation_is_not_a_loader_cycle_but_real_cycles_and_dangling_reject():
 p=clock_scene(cycle=True);pr=Compiler(providers=REG).compile(p);assert 'ability/peer/work' in pr.definitions and 'buff/peer/cycle' in pr.definitions
 p=clock_scene(cycle=True);p['buffs'][0]['on_remove']=[{'op':'trigger_ability','ability':'ability/peer/work'}]
 with pytest.raises(ValueError):Compiler(providers=REG).compile(p)
 for absent in [True,False]:
  p=clock_scene();p['entities'][0]['components']['abilities']=[]
  if absent:p['abilities']=[a for a in p['abilities'] if a['id']!='ability/peer/work']
  with pytest.raises(ValueError):Compiler(providers=REG).compile(p)


def test_bad_durations_and_unpossessed_runtime_targets_reject_without_mutation():
 for value in [-.125,True,float('nan')]:
  p=clock_scene();p['abilities'][1]['timeline'][0]['effect']['duration_seconds']=value
  with pytest.raises(ValueError):Compiler(providers=REG).compile(p)
 s=create(clock_scene());s.advance(1)
 for op in ['set_ability_cooldown','interrupt_ability']:
  before=s.checkpoint();effect={'op':op,'ability':'ability/peer/work'}
  if op=='set_ability_cooldown':effect['duration_seconds']=1.25
  with pytest.raises(ValueError):s.ctx.effects.execute('director',['director'],effect)
  assert s.checkpoint()==before


def test_late_recovery_rule_error_rolls_back_prior_health_events_cache_and_clock():
 p=clock_scene();p['rules'].append({'id':'rule/peer/negative_recovery','kind':'rule','contract':'ability.recovery','implementation':{'type':'expression','expression':'-1'}});p['abilities'][1]['timeline'][0]['effect']['rules']={'ability.recovery':'rule/peer/negative_recovery'};p['scenarioDraft']['commands']=[];s=create(p);s.advance(7);before=s.checkpoint()
 with pytest.raises(ValueError):
  with s.session.atomic():
   s.ctx.effects.execute('director',['worker'],{'op':'modify_resource','resource':'hp','delta':-127})
   s.ctx.effects.execute('director',['worker'],{'op':'set_ability_cooldown','ability':'ability/peer/work','duration_seconds':1.25,'rules':{'ability.recovery':'rule/peer/negative_recovery'}})
 assert s.checkpoint()==before


def test_source_Flame_10point6_deadline_exact20_packets_current_ATK800_RES35():
 p=flame_scene();bb=next(b for b in p['buffs'] if b['id']=='buff/ch9/flame/casting_state')['metadata']['source_BB'];assert (bb['duspfr_flame[cd].duration'],bb['duspfr_flame[cd].interval'],bb['duspfr_flame[cd].cooldown'])==(10.6,6,10)
 s=proof(p,'flame_full',179,320);hits=events(s,'damage.accepted');assert [t for t,_ in hits]==[21+15*i for i in range(20)];assert [x['amount'] for _,x in hits]==pytest.approx([62.4]*20);assert [(t,x['loss']) for t,x in events(s,'elemental.loss.accepted')]==[(21+15*i,48) for i in range(20)];assert s.ctx.resources.current('victim','hp')==pytest.approx(31007-20*62.4);assert s.ctx.get('victim',('runtime','elemental','remaining','FIRE'))==40;assert s.ctx.get('flame',('runtime','cooldowns','ability/linked/fire'))==618;assert not any(x['active'] for x in s.ctx.attachments.state()['instances'].values());assert not any(b['definition']=='buff/ch9/flame/casting_state' for b in s.ctx.get('flame',('buffs','instances')))


def test_six_second_source_pulse_and_state_end_reset_have_separate_deadlines():
 s=create(flame_scene());s.advance(180);assert s.ctx.get('flame',('runtime','cooldowns','ability/linked/fire'))==0;s.advance(1);assert s.ctx.get('flame',('runtime','cooldowns','ability/linked/fire'))==480;s.advance(139);assert s.ctx.get('flame',('runtime','cooldowns','ability/linked/fire'))==618
 assert [(t,x['ready_at']) for t,x in events(s,'ability.cooldown.updated') if x['ability']=='ability/linked/fire']==[(0,0),(180,480),(318,618)]


def test_actual_external_stun_cancels_source_and_sets_ready334():
 s=proof(flame_scene(stun_at=34),'flame_stun',33,100);assert not events(s,'command.rejected');assert [t for t,_ in events(s,'damage.accepted')]==[21];assert [(t,x['loss']) for t,x in events(s,'elemental.loss.accepted')]==[(21,48)];assert s.ctx.get('flame',('runtime','cooldowns','ability/linked/fire'))==334;assert s.ctx.get('flame',('runtime','casts'))=={};assert not any(x['active'] for x in s.ctx.attachments.state()['instances'].values())


def test_target_health_zero_skips_EP_and_source_state_releases_at_contact():
 s=proof(flame_scene(hp=25),'flame_target_zero',20,30);assert [x['amount'] for _,x in events(s,'damage.accepted')]==[25];assert not events(s,'elemental.loss.accepted');assert not s.ctx.alive('victim');assert s.ctx.get('flame',('runtime','casts'))=={};assert s.ctx.get('flame',('runtime','cooldowns','ability/linked/fire'))==321;assert not any(b['definition']=='buff/ch9/flame/casting_state' for b in s.ctx.get('flame',('buffs','instances')))


def test_runtime_and_source_delta_guard():
 assert guard()==START;parent=ROOT.parent/'unpack_work/campaign_c9_foundation_v9_candidate/ark_sim';child=CAND/'ark_sim';changed=[p.relative_to(parent).as_posix() for p in parent.rglob('*') if p.is_file() and p.suffix in ('.py','.json') and p.read_bytes()!=(child/p.relative_to(parent)).read_bytes()];assert set(changed)=={'content/capabilities.py','content/compiler.py','content/dependencies.py','content/schemas.py','domains/effects.py','content/spatial_validation.py','domains/spatial.py','domains/tile_fields.py','domains/tile_mechanics.py'}
