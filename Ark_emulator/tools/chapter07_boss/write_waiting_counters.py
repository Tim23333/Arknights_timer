"""Actual HP0 waiting Aura and owned Immo action counters; no dead-source cast shortcut."""
from pathlib import Path
import json,sys,hashlib
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.contracts import thaw
 from tools.chapter07_boss.test_mechanism_v5 import package,deploy,kill,ev
 from tools.chapter07_boss.build_mechanism_v1 import OUT,UID
 from tools.campaign_streaming_evidence import export_events
 out=OUT/'required_waiting_counters';out.mkdir(exist_ok=True);results={}
 p=package();path=out/'aura.input.json';write(path,p);s=Engine.create(Compiler().compile(path),seed=7187);deploy(s);before=s.ctx.attributes.value('ally','atk');kill(s,5);s.session.advance(6)
 after=s.ctx.attributes.value('ally','atk');assert before==120 and after==100 and s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss')
 results['aura']={'actual_source_health':0,'actual_source_active':False,'actual_source_alive':True,'ally_atk_before':before,'ally_atk_waiting':after,'expected_reference_waiting':120,'required_gap':True,'scope':'OwnedGlobalAura continuation whileactualwaitingrebirth referencepolicy; notnativebodyequivalence','checkpoint':s.checkpoint(),'journal':export_events(out/'aura.events.jsonl',s),'input_sha256':sha(path)}
 aid='ability/'+UID+'/immo_action';natural='ability/'+UID+'/immo_natural';timer='buff/'+UID+'/immo_timer_probe';sid='selector/test/patrt/immo'
 def add_immo(p,waiting):
  c=p['entities'][0]['components'];c['abilities'] += [aid,natural]
  c['ability_arbitration']['entries'] += [{'ability':x,'priority':0,'attack_clock':False,'require_attack_control':False,'condition':'False','parameters':{}} for x in [aid,natural]]
  p['selectors'].append({'id':sid,'kind':'selector','region':{'type':'radius','radius':1.75},'filters':[{'tag':'player'},{'state':'alive'}],'limit':None})
  p['abilities'] += [{'id':aid,'kind':'ability','selector':sid,'cooldown_seconds':0,'activation':{'mode':'manual','parameters':{'auto_only':True,'blocks_attacks':False}},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':.0521,'damage_flags':{'source_attack_type':'SPLASH','ignore_for_sp':False}}}]},{'id':natural,'kind':'ability','initial_cooldown_seconds':9999,'cooldown_seconds':9999,'activation':{'mode':'manual','parameters':{'auto_only':True}},'timeline':[{'at':0,'effect':{'op':'trigger_ability','target':'source','ability':aid}}]}]
  p['buffs'].append({'id':timer,'kind':'buff','duration_seconds':60,'interval_seconds':.8,'removal':{'on_source_death':'retain','on_target_death':'retain'},'effects':[{'op':'trigger_ability','target':'source','ability':aid}]})
  if waiting:c['rebirth']['on_begin'].append({'op':'apply_buff','target':'source','buff':timer})
  else:c['buffs']['initial'].append(timer)
  p['manifest']['metadata']['immo_probe_scope']='Exactactionrawcooldown0 separatefrom naturalEnemySkill9999/init9999. Controlledtimer insertion; no arbitrary cooldownbypass ornativephase0 Immo claim. WaitingtrueHP0 usingpublicdamage.'
  return p
 for waiting in [False,True]:
  p=add_immo(package(),waiting);name='immo_waiting' if waiting else 'immo_active';path=out/(name+'.input.json');write(path,p);s=Engine.create(Compiler().compile(path),seed=7187);deploy(s)
  if waiting:kill(s,5)
  s.session.advance(31);started=[e for e in ev(s,'ability.started') if e['payload']['ability']==aid];rejected=[e for e in ev(s,'effect.inactive_rejected') if e['payload'].get('operation')=='trigger_ability']
  if waiting:assert not started and rejected and s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss')
  else:assert len(started)==1 and started[0]['time']==24
  results[name]={'actual_action_starts':[e['time'] for e in started],'actual_inactive_rejections':[thaw(e) for e in rejected],'actual_source_hp':s.ctx.resources.current('boss','hp'),'actual_source_active':s.ctx.active('boss'),'native_action_cooldown':0,'native_natural_skill_initial_cooldown':9999,'required_gap':waiting,'interpretation':'Sourceactionalias Immo_Rage bypasses parentnaturalEnemySkillclock bycontentseparation; remaininggenericgap onlyactualownedwaiting lifecycle ability authorization','input_sha256':sha(path),'journal':export_events(out/(name+'.events.jsonl'),s),'checkpoint':s.checkpoint()}
 report={'schema':'ark-sim/patrt-waiting-required-counters/v1','core':implementation_digest(),'source_closure_sha256':sha(OUT/'source.closure.json'),'native_source_fields':{'RebornTalent.keepAlive':0,'RebornTalent.detachAbilityWhenReborn':0,'GlobalAura.removeBuffIncludeReborning':0,'Reborning.ignoreIfOwnerDead':1,'ImmoAction.ignoreIfOwnerDead':1,'TriggerAbility.checkCanUseAblityFlag':False,'TriggerAbility.castDirectly':False,'Action.cooldown':0,'EnemySkill.initCooldown':9999,'Buff.interval':.8},'results':results,'runtime_modified':False,'source_health_granted':False,'projectile_permission_borrowed':False,'whole_stage_executed':False};path=out/'report.json';write(path,report);print(json.dumps({'report_sha256':sha(path),'aura_actual_waiting':after,'immo_active_starts':results['immo_active']['actual_action_starts'],'immo_waiting_starts':results['immo_waiting']['actual_action_starts']}))
if __name__=='__main__':main()
