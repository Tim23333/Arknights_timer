import sys,json,hashlib,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m86_immunity_environment_candidate';BASE=ROOT.parent/'unpack_work/campaign_m88_corrected_death_environment_candidate';CORE='6013ef4e0f94e188391fb2593d681914b95291862acea662f292200bb644a1f6';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME));sys.path.append(str(Path(__file__).parent))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m86_immunity_environment'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
 import pytest
 assert implementation_digest()==CORE and Path(sys.modules['ark_sim'].__file__).resolve().parent==RUNTIME/'ark_sim'
 files=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']];start={str(p.relative_to(RUNTIME)):sha(p) for p in files};composition=json.loads((OUT/'composition.json').read_bytes());parent_start=composition['parent_source_before'];cases=[];inputs=[];original=Compiler.compile
 def capture(self,p,*a,**k):
  path=OUT/f'input_{len(inputs):03d}.json'
  try:write(path,p);row={'path':str(path.relative_to(ROOT)),'sha256':sha(path),'representation':'JSON supplied to actual Compiler'}
  except TypeError:
   path=path.with_suffix('.repr.txt');path.write_text(repr(p),encoding='utf8');row={'path':str(path.relative_to(ROOT)),'sha256':sha(path),'representation':'Python repr, explicitly not a JSON runtime fixture'}
  inputs.append(row);return original(self,p,*a,**k)
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
 tests=['tools/experiments/m70_applicability/test_applicability.py','tools/experiments/m70_applicability/test_frost_source.py','tools/experiments/m76_death_projectiles/test_death.py','tools/experiments/m85_death_sequence/test_sequence.py','tests_v2/test_abilities.py','tests_v2/test_activation_controls.py','tests_v2/test_domain_rules.py','tests_v2/test_buff_mode_lifecycle.py','tools/experiments/m86_immunity_environment/test_frost_combo.py','tools/experiments/m86_immunity_environment/test_cross.py']
 Compiler.compile=capture
 try:code=pytest.main([*[str(ROOT/n) for n in tests],'-k','not optional_actual_epoch_change','-q'],plugins=[Results()])
 finally:Compiler.compile=original
 assert code==0
 from test_frost_combo import make
 s=make();s.advance(100);pin=write_ordered(OUT/'frost.ordered.json',s.checkpoint());r=Engine.restore(s.program,load_bound(OUT/'frost.ordered.json',pin));s.advance(142);r.advance(142);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();write(OUT/'frost.final.json',s.snapshot());write(OUT/'frost.replay.json',s.export_replay())
 from test_cross import fixture,request
 program=Compiler().compile(fixture());s2=Engine.create(program,seed=860072);s2.submit({'action':'skill','source':'target','ability':'ability/m86/silence'},at=1);s2.advance(3);h=write_ordered(OUT/'source_none.ordered.json',s2.checkpoint());r2=Engine.restore(program,load_bound(OUT/'source_none.ordered.json',h));s2.advance(2);r2.advance(2);assert s2.snapshot()==r2.snapshot()==replay(program,s2.export_replay()).snapshot();write(OUT/'source_none.final.json',s2.snapshot());write(OUT/'source_none.replay.json',s2.export_replay())
 patch=[];changed={}
 for p in files:
  old=BASE/p.relative_to(RUNTIME)
  if not old.exists() or old.read_bytes()!=p.read_bytes():
   name=str(p.relative_to(RUNTIME)).replace('\\','/');changed[name]=sha(p);patch+=list(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],p.read_text(encoding='utf8').splitlines(True),fromfile='a/'+name if old.exists() else '/dev/null',tofile='b/'+name))
 (OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8');write(OUT/'changed_files.json',changed)
 assert start=={str(p.relative_to(RUNTIME)):sha(p) for p in files} and implementation_digest()==CORE
 parent_after={name:{str(p.relative_to(Path(name))):sha(p) for p in (Path(name)/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']} for name in parent_start};assert parent_start==parent_after
 names=tests+['tools/candidates/m86_immunity_environment/prepare.py','tools/build_frostnova_rebirth_immunity_model.py','packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json','validation/campaign/m86_immunity_environment/composition.json','validation/campaign/m86_immunity_environment/compat_initial.log','validation/campaign/m86_immunity_environment/compat_final.log'];locks={name:sha(ROOT/name) for name in names};locks[str(Path(__file__).relative_to(ROOT))]=sha(Path(__file__))
 catalog=json.loads((RUNTIME/'ark_sim/rules/contracts.json').read_bytes());ids=[row['id'] for row in catalog['contracts']];assert len(ids)==len(set(ids))==96 and 'buff.applicability' in ids
 artifacts=[OUT/n for n in ['frost.ordered.json','frost.final.json','frost.replay.json','source_none.ordered.json','source_none.final.json','source_none.replay.json']]
 boss=s.session.world.resolve('boss');packets=[e for e in s.session.events if e['type']=='damage.accepted'];report={'schema':'ark-sim/immunity-environment-composition-review/v1','status':'passed_bounded_composition','core_before':CORE,'core_after':CORE,'actual_module':sys.modules['ark_sim'].__file__,'source_before':start,'source_after':start,'parent_source_before':parent_start,'parent_source_after':parent_after,'source_locks':locks,'catalog_count':96,'changed_files':changed,'cases':cases,'actual_inputs':inputs,'fixture_difference':{'preserved_original_test':'tools/experiments/m85_death_sequence/test_sequence.py::test_optional_actual_epoch_change_stops_future_specs_without_inventing_new_actor_epoch','parent_M76_expected':2,'M88_final_dead_adds_one_expected':3,'new_actual_combination_case':'test_future_epoch_guard_preserved_with_actual_final_dead_generation_increment','original_log':'validation/campaign/m86_immunity_environment/compat_initial.log','not_counted_as_passed':True},'frost':{'source_variant':'enemy_1505_frstar@0/9d1e3d01ef79ae3e','initial_hp':25000,'first_down_at':20,'restore_at':170,'restore_hp':25000,'same_actor':True,'source_phase_packets':[(e['time'],e['payload']['amount']) for e in packets if e['payload']['source']==boss],'chen_source_s1_packets':[(e['time'],e['payload']['amount']) for e in packets if e['payload'].get('ability')=='ability/m86/chen_source_s1'],'stun_seconds':1.5,'stun_index':0,'intrinsic_immunity':[0,12,16,25],'first_sleep_immunity_removed_by_true_rebirth':True,'second_phase_sleep_effective':True,'final_dead_at':240,'final_kills':s.ctx.state()['kills'],'final_combat_kill_count':len([e for e in s.session.events if e['type']=='combat.kill']),'chen_cast_fixture_atk':100,'synthetic_frost_stat_probe':True,'not_canonical_operator_or_native_attack_claim':True},'source_none':{'packets':[(e['time'],e['payload']['amount'],e['payload']['source']) for e in s2.session.events if e['type']=='damage.accepted'],'final_hp':150,'final_sp':3,'inactive_afterhook_suppressed':True,'source_none_and_origin_preserved':True},'public_checkpoint_resume_equal':True,'public_command_replay_equal':True,'public_files':{str(p.relative_to(ROOT)):sha(p) for p in artifacts},'scope':'M88 actual death attribution/generation/default-retire preserved byte-for-byte; M84 applicability and boundary system signature added via memory-resolved common-parent hunks. Effects shared iterator owns sourceNone hook filtering, no nonexistent alternate iterator invented.','remaining_scope':['Whole FrostNova normal/skill/blackice and real selected owned skill cooldown bindings are not in this source module','Chen ATK100/interval and external SP grants are explicit synthetic casting harness; source skill payment/frames/flag/duration genuine','Full suite/baseline/stage promotion and external receipt remain separate'],'client_verified':False,'formal_approved':False,'whole_stage_executed':False}
 write(OUT/'candidate_final.json',report);print(json.dumps({'core':CORE,'passed':len(cases),'report_sha256':sha(OUT/'candidate_final.json'),'patch_sha256':sha(OUT/'candidate.patch'),'catalog':96}))
if __name__=='__main__':main()
