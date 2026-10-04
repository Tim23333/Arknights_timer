"""Freeze exact three-file generic delta with actual source/noopt/Root peer receipts."""
import difflib,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';RUNTIME=ROOT.parent/'unpack_work/campaign_ballista_directional_v1_candidate';OUT=ROOT/'validation/campaign/chapter05_ballista_v1';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
PIN='49af646affbd800b2d65a25634700deb1444fcbc3e0d886516ad9509edab217b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==PIN;report=OUT/'verification_v2_final.json';assert sha(report)=='a217f470ac7de92efe030cfce4981b2074f8735bc860a11d3786c93db78b8550';r=json.loads(report.read_bytes());assert r['exitcode']==0 and len(r['cases'])==167 and all(x['outcome']=='passed' for x in r['cases']);assert r['guard_before']==r['guard_after']
 for name,pin in r['guard_after'].items():assert sha(Path(name))==pin,name
 noopt=OUT/'noopt_comparison.json';assert sha(noopt)=='7a30dace6e3966e2ef6bf84dd1fb3dc02991692046230ea119004f8cd2843f41';n=json.loads(noopt.read_bytes());assert n['all_values_equal_except_named_fingerprint_paths'] and n['difference_counts']=={'runtime_fingerprint':3}
 peer=ROOT/'validation/campaign/ballista_root_peer/initial.json';assert sha(peer)=='1a8d8fec4c96f3c618204064216e08cb08ef14ccc3ecffae88632db365ca7b41';assert json.loads(peer.read_bytes())['exitcode']==0
 module=ROOT/'packages/campaign/chapter05_predefines/runtime_ballista/module.v2.reference.json';assert sha(module)=='1860c0480922f5901106d95d1a32b90b646f7d81c14e0ab866c44973cb6b0a59';assert sha(RUNTIME/'ark_sim/rules/contracts.json')=='679ae41d4276865e1100fee6969d2ab1cb0ea913d50f63bc04a04dbf23b9f246';archive=OUT/'source_delta';dest=OUT/'freeze.json'
 if archive.exists() or dest.exists():raise ValueError('Preserve freeze')
 changes={};patch=[];allsource={}
 for p in sorted((RUNTIME/'ark_sim').rglob('*')):
  if not p.is_file() or p.suffix not in ('.py','.json'):continue
  rel=p.relative_to(RUNTIME);allsource[rel.as_posix()]=sha(p);old=BASE/rel
  if old.exists() and p.read_bytes()==old.read_bytes():continue
  changes[rel.as_posix()]=sha(p);target=archive/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);assert sha(target)==sha(p);patch.extend(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],p.read_text(encoding='utf8').splitlines(True),fromfile='a/'+rel.as_posix() if old.exists() else '/dev/null',tofile='b/'+rel.as_posix()))
 assert set(changes)=={'ark_sim/domains/providers.py','ark_sim/domains/projectiles.py','ark_sim/domains/ray_projectile_profiles.py'};patchpath=OUT/'generic_delta.patch';patchpath.write_text(''.join(patch),encoding='utf8',newline='');proofs=[report,noopt,peer,module,ROOT/'packages/campaign/chapter05_predefines/runtime_ballista/source.policy.json',OUT/'composition.json',patchpath,Path(__file__)];f={'role':'Author exact freeze with separate Root independent source receipt; combined new-core acceptance/promotion remains Root-owned','parent_v5_core':'7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90','core':PIN,'source_all':allsource,'changed_files':changes,'catalog_sha':sha(RUNTIME/'ark_sim/rules/contracts.json'),'proofs':{str(p):sha(p) for p in proofs},'author_compat_passed':167,'Root_independent_cases':6,'noopt_original0_1_custom850_60':'Three snapshots/full181937events0-1 only3 top runtime_fingerprint differences; all other actual values equal','original_failed_report_preserved':str(OUT/'verification_final.json'),'generic_delta_policy':'Common-v5 hunks only; provider import+2 registrations union with latest Root30e; no entire providers file overwrite, preserve new typed blocking settle/abilities and Faust/branch consumers','module_manifest_profiles':'metadata.native_predefined_profiles stagekeys exactrawsource; metadata.registered_keys ten5-10 exactaliases; dormant has actual noSP/layer/projectile beforeactivation','native_body_policy':'Explicit replaceable mapbound cardinal math with sourceFarthestPoint/geometry parameters retained; no client oracle claim','whole_stage_executed':False,'client_verified':False,'combined_core_accepted':False}
 dest.write_text(json.dumps(f,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':PIN,'freeze_sha':sha(dest),'delta_patch_sha':sha(patchpath),'changed':list(changes)}))
if __name__=='__main__':main()
