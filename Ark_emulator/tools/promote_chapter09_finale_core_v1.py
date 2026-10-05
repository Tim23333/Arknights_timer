"""Copy the exactly validated generic V2 source, preserving historical proofs."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAND=ROOT.parent/'unpack_work/campaign_c9_finale_joint_v1_candidate'
OLD='4d42e2b6cf646ebe2291d695f82d968e5d4669217069a37bcc8b2babb850f7a4'
NEW='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root.resolve())],cwd=ROOT,text=True).strip()


def inventory(root):
    return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file() and p.suffix in ('.py','.json') and 'validation' not in p.relative_to(root).parts}


def main():
    assert core(ROOT)==OLD and core(CAND)==NEW
    full_path=ROOT/'validation/campaign/chapter09_finale_full_v1/full.108.json';full=json.loads(full_path.read_bytes())
    assert sha(full_path)=='c49d788167c27369eed51090d7e01276a865c9910174d0cf380ef45ad59059a3'
    assert full['passed'] and full['exitcode']==0 and full['identity_stable'] and len(full['cases'])==1219
    assert not full['collection_skips'] and all(r['outcome']=='passed' for r in full['cases'])
    assert full['guards_start']==full['guards_end'] and all(sha(p)==h for p,h in full['guards_end'].items())
    assert all(Path(p).is_relative_to(CAND/'ark_sim') for p in full['actual_modules'].values())
    base_path=ROOT/'validation/campaign/chapter09_finale_full_v1/baseline/verification.identity.json';base=json.loads(base_path.read_bytes())
    assert sha(base_path)=='a396962ef944bcf60fea8bc254434b415e262d0bd3f8e28cb43711342265d646'
    assert base['passed'] and base['exit_code']==0 and base['identity_stable'] and base['implementation_sha256']==NEW
    assert base['source_at_start']==base['source_at_completion'] and all(sha(p)==h for p,h in base['source_at_completion'].items())
    peer_path=ROOT/'validation/campaign/chapter09_mandra_peer_v2/peer.final.v2.json';peer=json.loads(peer_path.read_bytes())
    assert sha(peer_path)=='bc597d8ca7ca66b2d7ec542cc49f03a30ba88ab0c4d0f17211465ff76cef5e0d'
    assert peer['core']==NEW and peer['actual_exit']==0 and peer['passed']==4 and peer['failed']==0
    assert peer['source_before_end_and_current_equal'] and not peer['comparison_exclusions']
    wave_path=ROOT/'validation/campaign/chapter09_wave_peer_v4/peer.final.v4.json';wave=json.loads(wave_path.read_bytes())
    assert wave['effective_gates']==2 and wave['actual_corrected_worker_exit']==0 and wave['source_guard_before_after_current_equal']
    freeze_path=ROOT/'validation/campaign/chapter09_finale_joint_v1/freeze.focused.v1.json';freeze=json.loads(freeze_path.read_bytes())
    assert freeze['source_before']==freeze['source_after']
    frozen={Path(p).relative_to('ark_sim').as_posix():h for p,h in freeze['source_after'].items()}
    assert frozen==inventory(CAND/'ark_sim')
    before=inventory(ROOT/'ark_sim');after=inventory(CAND/'ark_sim');assert not set(before)-set(after)
    changes=[p for p in after if before.get(p)!=after[p]]
    backup=ROOT.parent/'unpack_work/primary_4d42_before_chapter09_finale_v1'
    out=ROOT/'validation/campaign/chapter09_finale_primary_v1/promotion.json';assert not backup.exists() and not out.exists()
    shutil.copytree(ROOT/'ark_sim',backup/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    assert inventory(backup/'ark_sim')==before and core(backup)==OLD
    for relative in changes:
        p=ROOT/'ark_sim'/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(CAND/'ark_sim'/relative,p)
    assert inventory(ROOT/'ark_sim')==after and core(ROOT)==NEW
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'passed':True,'primary_before':OLD,'primary_after':NEW,'before':before,'after':after,'changed_files':changes,'backup':str(backup),'full_sha':sha(full_path),'baseline_sha':sha(base_path),'independent_Mandra_source_sha':sha(peer_path),'independent_wave_sha':sha(wave_path),'core_focused_freeze_sha':sha(freeze_path),'catalog':108,'scope':'Generic Buff capture, actor/route motion separation, source receiver requests, owned tile-task input and explicit ability rejection policy; game source parameters remain replaceable content','historical_stage_receipts_not_migrated':True,'running_frozen_candidates_not_modified':True,'old_failed_source_profiles_preserved':True,'existing_compact_validation_preserved':True,'whole_campaign_complete':False,'client_verified':False},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'primary_core':NEW,'changed_files':len(changes),'receipt_sha':sha(out)}))


if __name__=='__main__':main()
