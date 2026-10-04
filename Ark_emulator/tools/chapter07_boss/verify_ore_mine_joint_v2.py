"""Actual pinned source joint; controller is an explicit isolated test override."""
import argparse, hashlib, json, sys, traceback
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--runtime',required=True);args=parser.parse_args()
 sys.path.insert(0,str(Path(args.runtime).resolve()));sys.path.insert(1,str(ROOT))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.contracts import thaw
 from ark_sim.tools.replay import replay
 from tools.campaign_content_composition_v2 import compose_modules
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.chapter07_boss.policies_v2 import providers as boss_providers
 from tools.chapter07_predefines.policies_v1 import providers as ore_providers
 from tools.candidates.chapter07_foundation_v1.test_scenario_cards_v1 import package as card_scene
 out=ROOT/'packages/campaign/chapter07_boss/patrt/ore_mine_joint_v2';out.mkdir(exist_ok=True)
 paths=[ROOT/x for x in ['packages/campaign/chapter07_boss/patrt/source.consumer.v1.json','packages/campaign/chapter07_predefines_consumer/ore.module.v3.json','packages/campaign/chapter07_predefines_consumer/mine.module.v2.json','packages/campaign/chapter07_boss/demons/enemy_1084_sotidm.module.v1.json','packages/campaign/chapter07_ordinary_remaining/sotisd.module.v3.reference.json','packages/campaign/roster/fixed12.m26.reference_module.json']]
 before={str(p):sha(p) for p in paths};registry={**ore_providers(),**boss_providers()};s=None
 result={'status':'failed','runtime_sha256':implementation_digest(),'guards_before':before,'scope':'Source mechanisms under explicit existing-actor controller fixture; fixed12 selection preserved, no native operator-skill or whole-stage/client proof'}
 try:
  assert implementation_digest()=='478db2509508490f920fb08d24b3656cc995230d87eec31ab35a5ef19cd6d5c9'
  mods=[(p.name,json.loads(p.read_bytes())) for p in paths];defs,provenance=compose_modules(mods)
  boss='unit/ch7/patrt/a53a85a6d0cd714f';demon=mods[3][1]['entities'][0]['id'];ordinary=mods[4][1]['entities'][0]['id'];controller='unit/char_151_myrtle';selector='selector/test/ch7/joint/boss'
  aid='ability/test/ch7/joint/firstdown';normal='ability/test/ch7/joint/plain';remove='ability/test/ch7/joint/remove_ore_immune'
  defs[controller]['components']['abilities'] += [aid,normal,remove]
  defs[selector]={'id':selector,'kind':'selector','region':{'type':'all'},'filters':[{'tag':'patriot_source'},{'state':'alive'}],'limit':1}
  for identifier,effects in [(aid,[{'op':'damage','damage_type':'true','scale':1000}]),(normal,[{'op':'damage','damage_type':'true','scale':1}]),(remove,[{'op':'remove_buff','buff':'buff/ch7/source/ore_immune'}])]:
   defs[identifier]={'id':identifier,'kind':'ability','selector':selector,'activation':{'mode':'manual','blocks_attacks':False},'timeline':[{'at':0,'effect':effect} for effect in effects]}
  scene=deepcopy(card_scene()['scenarioDraft']);scene.update(id='scene/test/ch7/patrt/ore_mine_joint',map={'rows':6,'cols':6},initialEntities=[{'definition':controller,'instanceAlias':'controller','position':{'row':0,'col':0}},{'definition':'unit/ch7/predefined/ore/level1','instanceAlias':'ore','position':{'row':3,'col':3}},{'definition':demon,'instanceAlias':'listener','position':{'row':3,'col':2}},{'definition':ordinary,'instanceAlias':'ordinary','position':{'row':2,'col':3}}])
  scene['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'max_wait_seconds':-1,'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':boss,'instanceAlias':'boss','position':{'row':3,'col':3}},'managed':True,'blocks_wave':True,'blocks_fragment':False,'delay_seconds':0,'count':1,'interval_seconds':0}]}]}]}
  fixture={'controller':controller,'initialPlacement':'Controlled fixture only, not a deployment/source-stage predefine','abilityOverride':[aid,normal,remove],'firstdownEffect':'Public owned manual fixture true damage scale1000; actor/source enemy attributes and HP/SP/durations unchanged','firstdownAt':5,'oreImmunityRemovalAt':1808,'mineDeployAt':1090,'not_native_operator_skill':True,'not_whole_stage_proof':True}
  p={'schemaVersion':2,'manifest':{'id':'package/test/ch7/patrt_ore_mine_joint_v2','requires':['preset/ark_standard'],'metadata':{'fixtureOverrides':fixture,'sourceProvenance':provenance}},'definitions':list(defs.values()),'scenarioDraft':scene}
  (out/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode())
  s=Engine.create(Compiler(providers=registry).compile(p),providers=registry,seed=7189)
  assert len(s.program.scenario['roster'])==12 and len(s.program.scenario['cards'])==1
  for tick,ability in [(5,aid),(1806,normal),(1808,remove)]:s.submit({'action':'skill','source':'controller','ability':ability},at=tick)
  s.submit({'action':'deploy','entity':'unit/ch7/predefined/mine/level1','row':3,'col':3,'alias':'mine'},at=1090)
  s.session.advance(236)
  assert s.ctx.get('listener',('behavior','state'))=='mode1'
  assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss')
  accepted=[e for e in s.session.events if e['type']=='damage.accepted'];oreid=s.session.world.resolve('ore');ordinaryid=s.session.world.resolve('ordinary')
  assert any(e['time']==229 and e['payload']['source']==oreid and e['payload']['target']==ordinaryid and e['payload']['amount']==500 for e in accepted)
  s.session.advance(1570)
  restored_hp=s.ctx.resources.current('boss','hp');assert abs(restored_hp-45000*.8500000238418579)<1e-6
  cp=out/'reborn1806.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=registry)
  s.session.advance(155);r.session.advance(155)
  h=replay(s.program,s.export_replay(),providers=registry);assert s.snapshot()==r.snapshot()==h.snapshot()
  bossid=s.session.world.resolve('boss');mineid=s.session.world.resolve('mine')
  accepted=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload'].get('target')==bossid]
  minehits=[e for e in accepted if e['payload'].get('source')==mineid];orehits=[e for e in accepted if e['payload'].get('source')==oreid]
  assert len(minehits)==1 and minehits[0]['time']==1839 and minehits[0]['payload']['amount']==3000
  assert len(orehits)==1 and orehits[0]['time']==1916 and orehits[0]['payload']['amount']==750
  # Mine's surviving vulnerability remains a real modifier: explicitfalse bypasses only invulnerability.
  assert not any(e['time']==1806 for e in accepted)
  assert s.ctx.resources.current('system/battle','stock_ch7_mine')==14 and s.ctx.resources.current('system/battle','dp')==5
  result.update(status='passed',cp_tick=1806,end_tick=1961,cp_equal=True,head_equal=True,restored_hp=restored_hp,mine_packets=[thaw(e) for e in minehits],ore_packets=[thaw(e) for e in orehits],fixtureOverrides=fixture)
 except Exception as exc:
  result.update(error=repr(exc),traceback=traceback.format_exc())
 finally:
  if s is not None:
   for name,data in [('events.json',thaw(s.session.events)),('replay.json',thaw(s.export_replay()))]: (out/name).write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode())
  result['guards_after']={str(p):sha(p) for p in paths};result['guards_equal']=before==result['guards_after']
  (out/'report.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'status':result['status'],'report':str(out/'report.json'),'sha256':sha(out/'report.json'),'error':result.get('error')}))
 return 0 if result['status']=='passed' and result['guards_equal'] else 1
if __name__=='__main__':raise SystemExit(main())
