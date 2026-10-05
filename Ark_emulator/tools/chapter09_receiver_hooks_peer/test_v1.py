from tools.chapter09_receiver_hooks_peer.fixture import *
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=16381947)
def events(s,t):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==t]
def proof(p,name,splits=[14,18],end=30):
 a=create(p);a.advance(end);b=create(p);LOG.mkdir(parents=True,exist_ok=True);pins=[]
 for i,t in enumerate(splits):
  b.advance(t-b.session.time);path=LOG/(name+str(i)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append(pin);b=Engine.restore(b.program,load_bound(path,pin),providers=REG)
 b.advance(end-b.session.time);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'core':CORE,'actual_CPP_head_full_equal':True,'CP_SHAs':pins,'input_digest':digest(p),'events':len(a.session.events)},indent=2),encoding='utf8');return a

@pytest.mark.parametrize('profile,ratio',[('native_literal',.20000000298023224),('prts_reference',1)])
def test_nonlethal_actual_same_modifier_clear_then_ordinary_inside1sec_rebirth(profile,ratio):
 p=gargoyle(profile);s=create(p);s.advance(14);assert s.ctx.resources.current('enemy','hp')==HP-677;assert not any(x['definition']==MARK for x in s.ctx.get('enemy',('buffs','instances')));s=proof(p,'native_same_modifier_'+profile);assert s.ctx.alive('enemy');assert abs(s.ctx.resources.current('enemy','hp')-HP*ratio)<1e-7;assert not events(s,'entity.rebirth.skipped')


def test_source_lethal_marker_precedes_actual_zero_skip_mode3_and_clear():
 p=gargoyle(damage=23000,ordinary_tick=None);s=proof(p,'native_mark_skip');assert not s.ctx.alive('enemy');assert s.ctx.resources.current('enemy','mode')==3;assert len(events(s,'entity.rebirth.skipped'))==1;records=list(s.session.events);mark=next(e for e in records if e['type']=='buff.applied' and e['payload']['buff']==MARK);zero=next(e for e in records if e['type']=='resource.changed' and e['payload']['target']==s.session.world.resolve('enemy') and e['payload']['resource']=='hp' and e['payload']['value']==0);assert mark['time']==zero['time']==13 and mark['id']<zero['id'];assert not any(x['definition']==MARK for x in s.ctx.get('enemy',('buffs','instances')))

@pytest.mark.parametrize('mode',['absent','inactive','expiry','holder_inactive'])
def test_actual_source_Buff_absent_inactive_expired_or_holder_hook_inactive_no_skip(mode):
 p=gargoyle(source_mode=mode,damage=23000,ordinary_tick=None);s=proof(p,'no_marker_'+mode);assert s.ctx.alive('enemy');assert not events(s,'entity.rebirth.skipped');assert not [x for _,x in events(s,'buff.applied') if x['buff']==MARK];assert abs(s.ctx.resources.current('enemy','hp')-HP*.20000000298023224)<1e-7


def test_receiver_exact_context_pre_health_post_order_no_hostwrite_and_CPP():
 s=proof(protocol(),'protocol_order',[16,18],35);assert s.ctx.resources.current('target','hp')==9933-619;assert s.ctx.resources.current('foreign','hp')==27307;records=list(s.session.events);pre=next(e for e in records if e['type']=='peer.receiver.pre');change=next(e for e in records if e['type']=='resource.changed' and e['time']==17);post=next(e for e in records if e['type']=='peer.receiver.post');assert pre['id']<change['id']<post['id'];assert pre['payload']['actual_source']==s.session.world.resolve('source');assert pre['payload']['holder']==s.session.world.resolve('target');assert events(s,'damage.accepted')[0][1]['ability']=='ability/peer/receiver_hit';assert not any(x['definition']==SIGNAL for x in s.ctx.get('target',('buffs','instances')))


def test_receiver_deny_no_holder_writes_and_pipeline_reject_still_cleanup():
 s=proof(protocol(deny=True),'request_deny',[16,18],35);assert s.ctx.resources.current('target','hp')==9933;assert not events(s,'peer.receiver.pre') and not events(s,'peer.receiver.post');assert not events(s,'damage.accepted')
 p=protocol();p['rules'].append({'id':'rule/peer/pipeline_reject','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'denied','expression':"{'accepted': False, 'amount': 619, 'allocations': [], 'events': []}"}],'output':'nodes.denied'}});p['abilities'][0]['rules']={'damage.pipeline':'rule/peer/pipeline_reject'};s=proof(p,'pipeline_reject_clear',[16,18],35);assert s.ctx.resources.current('target','hp')==9933;assert len(events(s,'peer.receiver.pre'))==len(events(s,'peer.receiver.post'))==1;assert not any(x['definition']==SIGNAL for x in s.ctx.get('target',('buffs','instances')));assert not events(s,'damage.accepted')

@pytest.mark.parametrize('options',[{'foreign':True},{'foreignop':True},{'overflow':True},{'badbool':True},{'hostwrite':True}])
def test_illegal_dynamic_holder_effects_records_or_host_mutation_atomic_reject(options):
 s=create(protocol(**options));s.advance(17);s.ctx.attributes.value('target','def');before=s.checkpoint()
 with pytest.raises((ValueError,TypeError)) as failure:
  ability=thaw(s.program.definitions['ability/peer/receiver_hit']);s.ctx.effects.execute('source',['target'],{'op':'damage','damage_type':'true','scale':1,'parameters':{'expected_tick':17}},ability=ability)
 assert s.checkpoint()==before
 text=str(failure.value)
 if options.get('foreign'):assert 'restricted to the actual holder' in text
 if options.get('foreignop'):assert 'finite holder Buff/emit writes' in text
 if options.get('overflow'):assert 'finite declared actor damage effects' in text
 if options.get('badbool'):assert 'boolean' in text or 'exact accepted/effect/effects' in text
 if options.get('hostwrite'):assert isinstance(failure.value.__cause__,TypeError) and 'item assignment' in text


def test_after_holder_Buff_late_random_fault_rolls_kernel_cache_RNG_and_all_marker():
 p=protocol();p['buffs'].append({'id':'buff/peer/receiver_fault','kind':'buff','effects':[{'op':'random','stream':'peer.receiver_late','probability':1,'on_success':[{'op':'emit','event':'peer.before_fault'}]},{'op':'modify_resource','resource':'missing','amount':1}]});p['buffs'][1]['damage_hooks'][0]['after_effects'].append({'op':'apply_buff','buff':'buff/peer/receiver_fault'});s=create(p);s.advance(17);s.ctx.attributes.value('target','def');before=s.checkpoint()
 with pytest.raises(ValueError,match='missing'):
  ability=thaw(s.program.definitions['ability/peer/receiver_hit']);s.ctx.effects.execute('source',['target'],{'op':'damage','damage_type':'true','scale':1,'parameters':{'expected_tick':17}},ability=ability)
 assert s.checkpoint()==before;assert not events(s,'peer.before_fault');assert s.session.random.samples==();assert not any(x['definition']==SIGNAL for x in s.ctx.get('target',('buffs','instances')));assert guard()==START


def test_compile_aftereffects_cannot_write_foreign_target_or_operation():
 for child in [{'op':'emit','event':'foreign','target':4},{'op':'damage','damage_type':'true','scale':1}]:
  p=protocol();p['buffs'][1]['damage_hooks'][0]['after_effects']=[child]
  with pytest.raises(ValueError):Compiler(providers=REG).compile(p)
 assert guard()==START
