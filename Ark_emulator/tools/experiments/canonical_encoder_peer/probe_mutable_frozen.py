"""Independent cache-boundary counterexample; no live/core/helper modification."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'))
from ark_sim.contracts.models import FrozenTuple,thaw
from ark_sim.adapters.api import implementation_digest
from tools.campaign_canonical_encoder import CanonicalEncoder
def main():
    source=ROOT/'tools/campaign_canonical_encoder.py';before=hashlib.sha256(source.read_bytes()).hexdigest();core=implementation_digest()
    child=[];malformed=tuple.__new__(FrozenTuple,(child,));encoder=CanonicalEncoder();first=b''.join(encoder.chunks(malformed));child.append(7);second=b''.join(encoder.chunks(malformed))
    expected=json.dumps(thaw(malformed),sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8')
    out={'schema':'ark-sim/encoder-cache-counterexample/v1','status':'actual_malformed_frozen_mutable_subtree_stale_bytes','core':core,
        'helper_sha256':before,'actual_module':sys.modules['ark_sim'].__file__,'construction':'tuple.__new__(FrozenTuple, (mutable_list,)) bypasses deep-freezing constructor; it remains a valid JSON tree',
        'first':first.decode('utf8'),'after_mutation_actual':second.decode('utf8'),'after_mutation_expected':expected.decode('utf8'),'cache':encoder.statistics(),
        'scope':'Malformed public Frozen wrapper boundary; normal deep-frozen runtime histories are not claimed affected','formal_approved':False}
    assert second!=expected and before==hashlib.sha256(source.read_bytes()).hexdigest() and core==implementation_digest()
    path=ROOT/'validation/campaign/canonical_encoder_peer/malformed_frozen_original_failure.json';path.write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'actual':second.decode(),'expected':expected.decode(),'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
if __name__=='__main__':main()
