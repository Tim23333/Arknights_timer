"""Required source consumer gate: known frozen4ef retained Cold payload failure."""
import json,hashlib
from pathlib import Path
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from tools.chapter06_units.snmage.test_module import fixture,deploy,sp,flags,damage
from tools.chapter06_units.snmage.build_module import OUT,SKILL

def test_required_source_retained_projectile_keeps_cold_payload_after_source_death():
    s=fixture(initial_sp=2);deploy(s)
    s.submit({'action':'skill','source':'target','ability':'ability/test/snmage/kill'},at=22)
    s.session.advance(25)
    actual={'source_alive':s.ctx.alive('mage'),'source_hp':s.ctx.resources.current('mage','hp'),'source_sp':sp(s),'target_flags':flags(s),'damage_packets':damage(s),'target_buffs':s.ctx.get('target',('buffs','instances'),[]),'projectile_events':[e for e in s.session.events if e['type'].startswith('projectile.')],'skill_starts':[e for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==SKILL]}
    expected={'source_alive':False,'damage_packets':[(22,8000),(23,300)],'target_required_cold_flag':23,'source_sp':0}
    src=OUT/'source.reference.json';module=OUT/'model.json'
    report={'schema':'ark-sim/ch6-snmage-required-retained-payload-failure/v1','core':implementation_digest(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'module_sha256':hashlib.sha256(module.read_bytes()).hexdigest(),'actual':actual,'expected':expected,'required_consumer_passed':23 in flags(s),'source_gap':'SimpleProjectile stopWhenSourceInvalid0 retains actual damage at23 but buff.application active-source gate rejects nested e2c_cold payload after source dies22','whole_stage_executed':False,'client_verified':False}
    dest=OUT/'retained_v12'/'required.retained_payload.actual.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((json.dumps(thaw(report),ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    assert damage(s)==[(22,8000),(23,300)] and not s.ctx.alive('mage') and sp(s)==0
    assert 23 in flags(s), 'Required retained native Cold payload was lost after source death'
