"""Publish exact four-file generic candidate only after all of its own gates."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate'
BACKUP=ROOT.parent/'unpack_work/primary_fb599_before_content_base_v2'
OUT=ROOT/'validation/campaign/content_base_v2_primary'
OLD='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b'
NEW='d509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def files(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts}


def core(root):
    text='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',text,str(root)],cwd=root,text=True).strip()


def main():
    assert core(ROOT)==OLD and core(CANDIDATE)==NEW
    pins={'baseline':('validation/campaign/content_base_v2/baseline.identity.json','a6afd2cc56c1d4d11cff01ee24765da9b44d520bbeb3faff759a99d3479a838a'),
          'independent':('validation/campaign/chapter06_common_primitives_v2_final_independent/verification.json','fbb91ba22f9430efecd8e8045dba67c5fa4d6666ce9f02ebe88658d7d1c6b9e6'),
          'independent_freeze':('validation/campaign/chapter06_common_primitives_v2_final_independent/freeze.json','65e07c64ef919679e77c3842ddb0d8fa1b874e4f4c4c5e9daddd2b271cb0d6fa'),
          'candidate_freeze':('validation/campaign/content_base_v2/freeze.json','8dc4d329bf18f8db73008395dcb6e5a7b31dc4cbc22ac6f355e04e3bc6510a13')}
    proofs={}
    for key,(rel,pin) in pins.items():assert sha(ROOT/rel)==pin;proofs[key]=json.loads((ROOT/rel).read_bytes())
    baseline=proofs['baseline'];assert baseline['passed'] and baseline['exit_code']==0 and baseline['identity_stable'] and baseline['implementation_sha256']==NEW
    assert baseline['source_at_start']==baseline['source_at_completion']
    for path,pin in baseline['source_at_completion'].items():assert sha(path)==pin,path
    assert sha(ROOT/'validation/campaign/content_base_v2/baseline.json')=='84f7fafd9126efb59b04be6f331feda5f19ac9f9abc5463b904c13f846ee7652'
    independent=proofs['independent'];assert independent['core']==NEW and independent['guards_equal']
    assert len(independent['cases'])==18 and all(c['outcome']=='passed' for c in independent['cases'])
    for path,pin in independent['guards_end'].items():assert sha(path)==pin,path
    suitefile=ROOT/'validation/campaign/content_base_v2/full_suite_v1/verification.json'
    suite=json.loads(suitefile.read_bytes());assert suite['core']==NEW and suite['exitcode']==0 and suite['identity_stable']
    assert suite['original_expectations_changed'] is False and not suite['collection_skips']
    assert len(suite['cases'])==1219 and all(c['outcome']=='passed' for c in suite['cases'])
    assert suite['guards_start']==suite['guards_end']
    for path,pin in suite['guards_end'].items():assert sha(path)==pin,path
    assert all(Path(p).is_relative_to(CANDIDATE/'ark_sim') for p in suite['actual_modules'].values())
    before=files(ROOT/'ark_sim');candidate=files(CANDIDATE/'ark_sim')
    changes={rel for rel,pin in candidate.items() if before.get(rel)!=pin}
    assert not set(before)-set(candidate)
    assert changes=={'domains/buffs.py','domains/no_source_damage.py','domains/tile_targets.py','domains/buff_application.py'}
    assert not BACKUP.exists() and not OUT.exists()
    shutil.copytree(ROOT/'ark_sim',BACKUP/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    assert files(BACKUP/'ark_sim')==before and core(BACKUP)==OLD
    for rel in changes:shutil.copyfile(CANDIDATE/'ark_sim'/rel,ROOT/'ark_sim'/rel)
    assert files(ROOT/'ark_sim')==candidate and core(ROOT)==NEW
    OUT.mkdir();report={'passed':True,'primary_before':OLD,'primary_after':NEW,'changed_files':sorted(changes),
        'backup':str(BACKUP),'before':before,'after':candidate,'proof_pins':pins,'actual_suite_sha':sha(suitefile),
        'scope':'Exact own-gated generic actorfree Buff packets, duration-aware Infinity plans, typed tile facts and wholeperiodic transaction. Old source/report identities remain separate.'}
    path=OUT/'promotion.json';path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'sha':sha(path)}))


if __name__=='__main__':main()
