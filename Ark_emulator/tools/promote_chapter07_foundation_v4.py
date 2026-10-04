"""Promote exact generic foundation bytes after their own immutable gates."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CAND=ROOT.parent/'unpack_work/campaign_finish_timeline_wave_v4_candidate'
OLD='d509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1'
NEW='4f16ac4c8ec0c0080302dfa1b6b1b6cc4da90d383ae9a2da5f796551d630c346'
CHANGES={'adapters/api.py','content/capabilities.py','content/compiler.py','content/schemas.py',
         'domains/abilities.py','domains/buffs.py','domains/context.py','domains/effects.py',
         'domains/movement.py','domains/rebirth.py','domains/selection.py','domains/shared_auras.py',
         'domains/timeline.py','domains/waiting_actions.py','kernel/session.py','rules/contracts.json'}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def files(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*')
    if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts}


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def read_guarded(rel,pin):
    p=ROOT/rel;assert sha(p)==pin,rel
    return json.loads(p.read_bytes())


def main():
    assert core(ROOT)==OLD and core(CAND)==NEW
    freeze=read_guarded('validation/campaign/finish_timeline_wave_v4/freeze.json',
                       '2e13dd935beae67f95d87be43470c38637e450af8dc59822db56053593da592f')
    assert freeze['core']==NEW
    for path,pin in freeze['files'].items():assert sha(path)==pin,path
    baseline=read_guarded('validation/campaign/finish_timeline_wave_v4/baseline.identity.json',
                         '0dbcaa5b3e31c1296318136e8fdc8343fba917d2995a491d75df39470e4dcb03')
    assert baseline['passed'] is True and baseline['exit_code']==0 and baseline['identity_stable'] is True
    assert baseline['implementation_sha256']==NEW and baseline['source_at_start']==baseline['source_at_completion']
    for path,pin in baseline['source_at_completion'].items():assert sha(path)==pin,path
    assert sha(ROOT/'validation/campaign/finish_timeline_wave_v4/baseline.json')=='d59d345511a07b986c819b3ce9a16d6dd211f97d18d938b113cbc8176e34949c'
    peer=read_guarded('validation/campaign/chapter07_wave_finish_independent_complete/freeze.json',
                     '7a8acbfe19729a36901690c53d736b40a9611cf5d3ec23b10d798a516795bb15')
    assert peer['passed'] is True and peer['guards_equal'] is True and peer['core']==NEW and peer['cases']==15
    for path,pin in peer['files'].items():assert sha(path)==pin,path
    for item in peer['reports']:
        report=read_guarded(item['path'],item['sha'])
        assert report['core']==NEW and report['exit']==0 and report['guards_equal'] is True
        assert report['cases'] and all(c['outcome']=='passed' for c in report['cases'])
    author=read_guarded('validation/campaign/finish_timeline_wave_v4/author_verification.json',
                       '4fd837dca32368067bd428bc43daff3fde87ff9ed12897fad2e8ac2b536fe157')
    assert author['actual_exit']==0 and author['core']==NEW and author['guards_equal'] is True
    assert len(author['cases'])==50 and all(c['outcome']=='passed' for c in author['cases'])
    for path,pin in author['guards_end'].items():assert sha(path)==pin,path
    suitefile=ROOT/'validation/campaign/finish_timeline_wave_v4/full_suite_v1/verification.json'
    suite=json.loads(suitefile.read_bytes())
    assert suite['passed'] is True and suite['exitcode']==0 and suite['core']==NEW and suite['identity_stable'] is True
    assert not suite['collection_skips'] and suite['original_expectations_changed'] is False
    assert len(suite['cases'])==1219 and all(c['outcome']=='passed' for c in suite['cases'])
    assert suite['guards_start']==suite['guards_end']
    for path,pin in suite['guards_end'].items():assert sha(path)==pin,path
    assert all(Path(p).is_relative_to(CAND/'ark_sim') for p in suite['actual_modules'].values())
    before=files(ROOT/'ark_sim');after=files(CAND/'ark_sim')
    assert not set(before)-set(after)
    changed={p for p,h in after.items() if before.get(p)!=h};assert changed==CHANGES
    backup=ROOT.parent/'unpack_work/primary_d509_before_chapter07_foundation_v4'
    out=ROOT/'validation/campaign/chapter07_foundation_v4_primary'
    assert not backup.exists() and not out.exists()
    shutil.copytree(ROOT/'ark_sim',backup/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    assert files(backup/'ark_sim')==before and core(backup)==OLD
    for rel in sorted(changed):shutil.copyfile(CAND/'ark_sim'/rel,ROOT/'ark_sim'/rel)
    assert files(ROOT/'ark_sim')==after and core(ROOT)==NEW
    out.mkdir();p=out/'promotion.json';p.write_text(json.dumps({'passed':True,
        'primary_before':OLD,'primary_after':NEW,'changed_files':sorted(changed),
        'backup':str(backup),'before':before,'after':after,'own_suite_sha':sha(suitefile),
        'baseline_guard_sha':sha(ROOT/'validation/campaign/finish_timeline_wave_v4/baseline.identity.json'),
        'peer_freeze_sha':sha(ROOT/'validation/campaign/chapter07_wave_finish_independent_complete/freeze.json'),
        'scope':'Own-gated generic declared WaitingActions/shared Aura/actual target tiles, boundary cache consistency and finite actor-owned wave finish. Oldsource reports retain oldidentity; no wholeC7 or userclient accuracy claim.'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'core':NEW,'sha':sha(p)}))


if __name__=='__main__':main()
