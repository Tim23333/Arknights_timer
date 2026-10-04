"""Source explicit false bypasses only Invul hook, not all target modifiers."""
import json
from ark_sim import Compiler,Engine
from tools.chapter07_boss.test_spear_v2 import package as original,deploy,ev
from tools.chapter07_boss.build_mechanism_v1 import OUT,UID
from tools.chapter07_boss.policies_v2 import providers
def package(half=False):
 q=original();p=json.loads((OUT/'combined.mechanism.v2.json').read_bytes());p['entities']+=q['entities'][1:];p['scenarioDraft']=q['scenarioDraft']
 for b in ['abilities','selectors']:p[b]+=[d for d in q[b] if d['id'].startswith(('ability/test/','selector/test/'))]
 inv='buff/'+UID+'/invulnerable';p['entities'][0]['components']['buffs']['initial'].append(inv)
 aid='ability/test/patrt/orelike';p['abilities'].append({'id':aid,'kind':'ability','selector':'selector/test/patrt/boss','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','parameters':{'amount':500,'consider_unhurtable':False},'damage_flags':{'source_attack_type':'NONE','ignore_for_sp':False}}}]});p['entities'][1]['components']['abilities'].append(aid)
 if half:
  rid='rule/test/patrt/half';buff='buff/test/patrt/half';p['rules'].append({'id':rid,'kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':inputs.effect.settlement.accepted,'amount':inputs.effect.settlement.amount * .5,'allocations':[],'events':[]}"}],'output':'nodes.result'}});p['buffs'].append({'id':buff,'kind':'buff','damage_hooks':[{'phase':'after','rule':rid}]});p['entities'][0]['components']['buffs']['initial'].append(buff)
 p['manifest']['metadata']['controlled_invulnerability_fixture']='Native15s invul installedinitially onlyto isolate damagecondition; notclaimnewnativephase placement';return p
def make(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=7187)
def test_actual_plain_unhurtable_rejected_but_sourceexplicitfalse_true500_accepted():
 s=make(package());deploy(s);s.submit({'action':'skill','source':'hero','ability':'ability/test/patrt/kill'},at=1);s.submit({'action':'skill','source':'hero','ability':'ability/test/patrt/orelike'},at=2);s.session.advance(3)
 assert s.ctx.resources.current('boss','hp')==44500 and not ev(s,'entity.rebirth.started')
 assert [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted') if e['payload'].get('target')==s.session.world.resolve('boss')]==[(2,500)]
def test_actual_considerfalse_still_runs_other_target_damage_modifiers():
 s=make(package(True));deploy(s);s.submit({'action':'skill','source':'hero','ability':'ability/test/patrt/orelike'},at=2);s.session.advance(3);assert s.ctx.resources.current('boss','hp')==44750
