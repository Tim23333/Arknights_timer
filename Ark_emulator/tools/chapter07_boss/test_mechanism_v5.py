"""Actual public four-hit / rebirth probes; quarantined from stage delivery."""
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter07_boss.build_mechanism_v1 import ROOT,OUT,UID,N,MARKER
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def package():
 p=json.loads((OUT/'mechanism.v3.json').read_bytes());hero='unit/test/patrt/hero';kill='ability/test/patrt/kill'
 p['entities'].append({'id':hero,'kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':1000000,'atk':100000,'def':100,'mres':0,'block_count':3,'taunt_level':0}},'resources':{'hp':{'initial':1000000,'capacity':1000000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[kill]}})
 p['entities'].append({'id':'unit/test/patrt/ally','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':1000,'atk':100,'def':50}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
 p['selectors'].append({'id':'selector/test/patrt/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'patriot_source'},{'state':'alive'}],'limit':1})
 p['abilities'].append({'id':kill,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/patrt/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
 p['scenarioDraft']={'id':'scene/ch7/patrt/mechanism','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':7},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':20,'capacity':99}},'initialEntities':[{'definition':UID,'instanceAlias':'boss','position':{'row':2,'col':2},'route':{'motionMode':'WALK','startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':5},'checkpoints':[]}},{'definition':'unit/test/patrt/ally','instanceAlias':'ally','position':{'row':4,'col':6}}],'roster':[hero]};return p
def make(p=None):return Engine.create(Compiler().compile(p or package()),seed=7187)
def deploy(s):s.submit({'action':'deploy','definition':'unit/test/patrt/hero','alias':'hero','position':{'row':2,'col':2}},at=0)
def kill(s,at):s.submit({'action':'skill','source':'hero','ability':'ability/test/patrt/kill'},at=at)
def ev(s,name):return [e for e in s.session.events if e['type']==name]
def test_actual_phase0_profile_aura_shield_and_four_independent_packets():
 s=make();deploy(s);s.session.advance(29)
 assert s.ctx.attributes.value('boss','atk')==2720 and s.ctx.attributes.value('boss','def')==2100 and s.ctx.attributes.value('boss','mres')==90
 assert s.ctx.attributes.value('ally','atk')==120 and s.ctx.attributes.value('ally','def')==250
 assert not any(b['definition']==MARKER for b in s.ctx.get('ally',('buffs','instances'),[])) # explicitlyunsupportedsharedmarker, notsourceproducerpass
 packets=[e for e in ev(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss')];assert [(e['time'],e['payload']['amount']) for e in packets]==[(19,2620),(22,2620),(25,2620),(28,2620)]
 assert s.ctx.resources.current('hero','hp')==1000000-4*2620
def test_actual_unblocked_null_attack_mode_never_uses_range_fallback():
 p=package();p['entities'][1]['components']['attributes']['base']['block_count']=0;s=make(p);deploy(s);s.session.advance(150)
 assert not [e for e in ev(s,'ability.started') if e['payload'].get('source')==s.session.world.resolve('boss')]
def test_actual_native60s_ratio85_restore_then15_invul_no_frost_shortcut():
 s=make();deploy(s);kill(s,5);s.session.advance(6)
 assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss') and len(ev(s,'entity.rebirth.started'))==1
 s.session.advance(1799);assert s.ctx.resources.current('boss','hp')==0
 s.session.advance(1);assert s.ctx.resources.current('boss','hp')==pytest.approx(45000*.8500000238418579)
 assert s.ctx.attributes.value('boss','atk')==2240 and s.ctx.attributes.value('boss','def')==900
 kill(s,1806);s.session.advance(2);assert s.ctx.alive('boss')
 s.session.advance(448);kill(s,2256);s.session.advance(2);assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.alive('boss') and len(ev(s,'entity.died'))==1
@pytest.mark.parametrize('tick',[20,6])
def test_actual_partial_mechanism_cp_and_head_with_explicit_pending_scope(tick,tmp_path):
 s=make();deploy(s)
 if tick==6:kill(s,5)
 s.session.advance(tick);p=tmp_path/'patrt.json';h=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,h));end=40 if tick==20 else 1807;s.session.advance(end-tick);r.session.advance(end-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
