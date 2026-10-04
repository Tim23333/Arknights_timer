"""Supplemental actual incoming packets witness DEF doubling and expiry."""
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.witness_canonical_roster_trio import ROOT,PACKAGE,actor,scene,make,command,events,eq,finish,sha


def probe():
    data=scene([actor('lisk',sp=18)])
    enemy=next(e for e in data['entities'] if e['id']=='unit/witness_enemy')
    enemy['components']['abilities'].append('ability/witness_large_physical')
    data['abilities'].append({'id':'ability/witness_large_physical','kind':'ability',
        'activation':{'mode':'manual'},'selector':'selector/witness_player',
        'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical','scale':2}}]})
    sim=make(data)
    command(sim,'enemy','ability/witness_hit_true',at=1)
    command(sim,'enemy','ability/witness_large_physical',at=2)
    command(sim,'enemy','ability/witness_large_physical',at=240)
    sim.advance(3)
    eq(sim.ctx.resources.current('lisk','hp'),3124-(2000-731*2))
    eq(sim.ctx.resources.current('lisk','sp'),0)
    sim.advance(238)
    damages=events(sim,'damage.accepted')
    assert [(e['time'],e['payload']['amount']) for e in damages]==[(1,0),(2,538),(240,1269)]
    eq(sim.ctx.resources.current('lisk','hp'),1317)
    eq(sim.ctx.resources.current('lisk','sp'),2)
    eq(sim.ctx.resources.current('lisk','shield_charge'),0)
    return finish(sim)


def main():
    from ark_sim.adapters.api import implementation_digest
    test=ROOT/'tests_v2/test_canonical_lisk_defense.py'
    files=[PACKAGE,test,Path(__file__),ROOT/'tools/witness_canonical_roster_trio.py',ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/skills.liskam.json']
    before={str(p):sha(p) for p in files};core=implementation_digest()
    actual=probe()
    result=subprocess.run([sys.executable,'-m','pytest',str(test),'-q'],cwd=ROOT,capture_output=True,text=True)
    after={str(p):sha(p) for p in files};stable=before==after and core==implementation_digest()
    passed=stable and result.returncode==0
    out={'schema':'ark-sim/campaign-mechanism-test-evidence/v1','passed':passed,
        'implementation_sha256':core,'identity_stable':stable,'input_package':str(PACKAGE),'input_package_sha256':before[str(PACKAGE)],
        'tests':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'source_sha256':before[str(p)],'result':'passed' if passed else 'failed'} for p in files[1:4]],
        'source_hashes':before,'pytest_output':result.stdout+result.stderr,'actual':actual,
        'independent_expected_packets':[[1,0],[2,538],[240,1269]],'formal_approval':False,'review_receipt':False,
        'scope':'Liskarm canonical DEF+100%, shield and half-open8s only','client_pending_preserved':True}
    path=ROOT/'validation/campaign/canonical_lisk_defense.m8_roster.json'
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':passed,'output':str(path)}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
