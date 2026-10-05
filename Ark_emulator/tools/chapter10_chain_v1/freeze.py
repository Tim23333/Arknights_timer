"""Freeze source hashes of the isolated chain candidate and its compact proofs."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=(ROOT/'../unpack_work/campaign_c10_chain_v1_candidate').resolve()
OUT=ROOT/'validation/campaign/chapter10_chain_v1/frozen.v1.json'
EXPECTED='09c265c4a5f8d849f20d08a0e073db558d8d6a727f1060f3ad2a63cec2e1f7c6'
BASE='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):
    return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=ROOT,text=True).strip()
def main():
    assert core(CAND)==EXPECTED
    assert core(ROOT)==BASE,'Primary changed: re-check parent provenance before freeze'
    author=ROOT/'validation/campaign/chapter10_chain_v1/author.v1.json'
    native=ROOT/'validation/campaign/chapter10_chain_v1/native.scope.v1.json'
    for p in (author,native):
        r=json.loads(p.read_bytes());assert r['passed'] and r['implementation']==EXPECTED
    changed=[]
    for p in sorted((CAND/'ark_sim').rglob('*')):
        if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts and 'validation' not in p.parts:
            original=ROOT/p.relative_to(CAND)
            if not original.exists() or sha(p)!=sha(original):changed.append({'candidate':str(p),'sha256':sha(p),'parent':str(original),'parent_sha256':sha(original) if original.exists() else None})
    guards={str(p):sha(p) for p in sorted((ROOT/'tools/chapter10_chain_v1').glob('*.py'))}
    result={'schema':'ark-sim/finite-chain-frozen/v1','primary':BASE,'implementation':EXPECTED,
        'candidate_root':str(CAND),'changed_sources':changed,'owned_tool_sources':guards,
        'actual_author':{'path':str(author),'sha256':sha(author)},'actual_native_scope':{'path':str(native),'sha256':sha(native)},
        'source_provenance':'validation/campaign/chapter10_chain_v1/native_source.v1.json',
        'module_interface':'tools/chapter10_chain_v1/native_module.py: build_fragment / mount',
        'full_suite_status':'separate leased actual run in progress; no passed claim yet',
        'baseline_status':'separate leased actual run in progress; no passed claim yet',
        'actual_game_accuracy_verified':False,'primary_modified':False,'formal_approval':False}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'core':EXPECTED,'changed_count':len(changed),'freeze_sha256':sha(OUT)}))
if __name__=='__main__':main()
