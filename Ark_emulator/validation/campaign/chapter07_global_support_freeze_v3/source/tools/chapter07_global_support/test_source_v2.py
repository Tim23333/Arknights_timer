"""Literal commander source values and unlike-Patriot contribution identities."""
import json,sys
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_finish_timeline_wave_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
MODULE=ROOT/'packages/campaign/chapter07_global_support/sotidp.module.v2.json';MARKER='buff/ch7/source/enemy_9D0_talent_strength';ATTRIBUTE='buff/ch7/source/enemy_9D0_talent_strength[attribute]';OUT=ROOT/'validation/campaign/chapter07_global_support_v2'
def package(two=False):
 assert implementation_digest()=='4f16ac4c8ec0c0080302dfa1b6b1b6cc4da90d383ae9a2da5f796551d630c346';p=json.loads(MODULE.read_bytes());unit=p['entities'][0]['id'];p['entities'].append({'id':'unit/global/receiver','kind':'entity','tags':['enemy','ground','receiver'],'components':{'attributes':{'base':{'atk':100,'def':50,'max_hp':1000,'mres':0}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});initial=[{'definition':unit,'instanceAlias':'commander1','position':{'row':0,'col':0}},{'definition':'unit/global/receiver','instanceAlias':'receiver','position':{'row':0,'col':3}}]
 if two:initial.insert(1,{'definition':unit,'instanceAlias':'commander2','position':{'row':0,'col':1}})
 p['scenarioDraft']={'id':'scene/global/sotidp','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},'objectives':{},'initialEntities':initial};return p
def child(s,definition):return [i for i in s.ctx.entity('receiver')['components']['buffs']['instances'] if i['definition']==definition]
def test_one_exact_source_commanders_self_no_SP_and_global10percent100DEF():
 s=Engine.create(Compiler().compile(package()));a=s.ctx.entity('commander1')['components']['attributes']['base'];assert (a['max_hp'],a['atk'],a['def'],a['mres'],a['move_speed'],a['attack_interval'])==(7000,300,120,50,1,2.7);assert set(s.ctx.entity('commander1')['components']['resources'])=={'hp'};assert s.ctx.attributes.value('receiver','atk')==110.00000000000001 and s.ctx.attributes.value('receiver','def')==150;assert s.ctx.attributes.value('commander1','atk')==330 and s.ctx.attributes.value('commander1','def')==220;assert len(child(s,ATTRIBUTE))==1 and len(child(s,MARKER))==1
def test_two_sources_attr2_modifiers_but_one_marker_then_realwithdraw_anddeath():
 s=Engine.create(Compiler().compile(package(True)));assert s.ctx.attributes.value('receiver','atk')==120 and s.ctx.attributes.value('receiver','def')==250;assert len(child(s,ATTRIBUTE))==2 and len(child(s,MARKER))==1 and len(child(s,MARKER)[0]['aura_leases'])==2;uid=child(s,MARKER)[0]['id'];s.ctx.lifecycle.retire('commander1','withdrawn');assert s.ctx.attributes.value('receiver','atk')==110.00000000000001 and s.ctx.attributes.value('receiver','def')==150;assert len(child(s,ATTRIBUTE))==1 and child(s,MARKER)[0]['id']==uid;s.ctx.effects.execute('receiver',[s.session.world.resolve('commander2')],{'op':'damage','damage_type':'true','scale':0,'additions':7000});assert not child(s,ATTRIBUTE) and not child(s,MARKER) and s.ctx.attributes.value('receiver','atk')==100
def test_source_typed_camo_and_opposite_side_never_receive_buffs():
 p=package();p['entities'][-1]['components']['selection_state']['camouflage']=True;s=Engine.create(Compiler().compile(p));assert not child(s,ATTRIBUTE) and not child(s,MARKER);p=package();p['entities'][-1]['components']['selection_state']['side']=0;s=Engine.create(Compiler().compile(p));assert not child(s,ATTRIBUTE) and not child(s,MARKER)
def test_two_sources_real_public_release_CP_head():
 p=package(True);p['selectors'].append({'id':'selector/global/first','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':2}}]});p['scenarioDraft']['scheduledEffects']=[{'at':8,'effect':{'op':'retire','selector':'selector/global/first','parameters':{'reason':'withdrawn'}}}];program=Compiler().compile(p);s=Engine.create(program);s.session.advance(5);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'two5.cp.json';assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.session.advance(10);r.session.advance(10);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot();assert len(child(s,ATTRIBUTE))==1 and len(child(s,MARKER))==1;(OUT/'actual.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2)+'\n',encoding='utf8',newline='')
