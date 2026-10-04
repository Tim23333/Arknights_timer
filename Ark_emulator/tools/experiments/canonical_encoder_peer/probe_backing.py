from pathlib import Path
import json,sys,hashlib
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'))
from ark_sim.contracts.models import FrozenMapping,thaw
from tools.campaign_canonical_encoder import CanonicalEncoder
def main():
    path=ROOT/'tools/campaign_canonical_encoder.py';before=hashlib.sha256(path.read_bytes()).hexdigest();backing={'k':1};bad=object.__new__(FrozenMapping);object.__setattr__(bad,'_data',backing)
    e=CanonicalEncoder();first=b''.join(e.chunks(bad));backing['k']=2;second=b''.join(e.chunks(bad));expected=json.dumps(thaw(bad),separators=(',',':')).encode()
    backing['k']=float('nan');third=b''.join(e.chunks(bad));report={'schema':'ark-sim/encoder-backing-counterexample/v1','status':'actual_mutable_frozen_backing_stale_cache_after_deep_revision','helper_sha256':before,
        'construction':'public FrozenMapping allocated via object.__new__; _data set once to externally retained mutable backing. Primitive children alone do not make backing immutable.',
        'first':first.decode(),'actual_after_mutation':second.decode(),'expected_after_mutation':expected.decode(),'actual_after_nonfinite':third.decode(),'expected_after_nonfinite':'JSON encoding raises ValueError',
        'statistics':e.statistics(),'scope':'malformed public wrapper only; no assertion of mutation in existing normal runtime history','formal_approved':False}
    assert second!=expected and before==hashlib.sha256(path.read_bytes()).hexdigest()
    out=ROOT/'validation/campaign/canonical_encoder_peer/mutable_backing_deep_revision_failure.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual':second.decode(),'expected':expected.decode(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
if __name__=='__main__':main()
