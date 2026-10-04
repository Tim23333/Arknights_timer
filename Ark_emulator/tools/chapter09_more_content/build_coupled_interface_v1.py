"""Source-only coupled interface; explicit rejection until full traits are authored."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.chapter09_more_content.build_v1 import SOURCE,FREEZE,OUT,sha
import json
def main():
 data=json.loads(SOURCE.read_bytes());rows=[]
 for key in ('enemy_1174_duholy','enemy_1175_dushdo'):
  vid,row=next((k,v) for k,v in data['variants'].items() if v['prefab_key']==key)
  cs=data['prefabs'][key]['components'];prefab=data['prefabs'][key]
  rows.append({'variant':vid,'blackboard':row['native_enemy']['resolved']['talentBlackboard'],'mode_nodes':row['modes'],'passive_closure':row['passive_and_skill_components'],'components':cs,'aura_colliders':[g for g in prefab['geometry_sources'] if g['unity_type']=='CircleCollider2D'],'runtime_authored':False,'admitted':False})
 p={'schema':'ark-sim/c9-coupled-source-interface/v1','source_locks':{str(x):sha(x) for x in (SOURCE,FREEZE)},'actors':rows,'transitive_trigger':data['bson_templates']['templates']['enemy_dushdo_duholy_trigger']['parsed'],'required_actual_interfaces':[
 {'domain':'aura/qualification','source':'FilterBuffTargetValidator _buffs duholy_mask/dushdo_mask, source checks disabled','contract':'Select live typed same-side character ground/air from actual collider; self EXCLUDE; query active marker instances; reconcile per-source leases on exit/retire.'},
 {'domain':'buff.start/remove trait transition','source':'enemy_dushdo_duholy_trigger ON_BUFF_START/ON_BUFF_FINISH CheckContainsBuff then IfNot then TriggerAbility/InterruptAbility traitAbility','contract':'One peer marker lease prevents duplicate trait activation; last peer removal interrupts exact named trait with _stopAffect false. Full source ability attachment and duration/action closure must be authored.'},
 {'domain':'duholy debuff','source':'duholy_auraAbility attributeType7/formula0 BB traitAbility.attack_speed=-30; traitAbility.range_radius=1.1; taunt_level0','contract':'Resolve true trait mode/ability ownership and radius loading before applying ASPD flat conversion. Preserve actual field mapping, no name-based inference.'},
 {'domain':'dushdo invisibility','source':'ToggleablePassiveBuffAbility dushdo_invisible abnormalFlag9; AdvancedCompoundToggleChecker init1, disableWhenAttack1, disableWhenBlocked1, restoreDelay3','contract':'Bind actual attack event/blocker lifecycle to passive toggle, union source status9, retime delayed restore and CP/head pending jobs; no guessed camouflage substitute.'},
 {'domain':'dushdo attack time','source':'dushdo_traitAbility[BaseAttackTimeDown] attributeType8/formula0 BB traitAbility.base_attack_time=-1.2','contract':'Trait active changes base attack time by -1.2; must integrate actual running recovery/timing rule semantics and removal.'}],
 'unsupported_policy':'build_v1.build rejects both keys until every listed closure is implemented; no empty Buff or partial actor emitted. Source-only interface is not compile/model/stage acceptance.','whole_stage':False,'client_verified':False}
 path=OUT/'coupled.source.interface.v1.json';path.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(path,sha(path))
if __name__=='__main__':main()
