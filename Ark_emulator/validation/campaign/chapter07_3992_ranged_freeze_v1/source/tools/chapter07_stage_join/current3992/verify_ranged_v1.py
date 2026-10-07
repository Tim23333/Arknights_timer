"""Fresh current core source assertions and motion-boundary guards."""
import sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];CAND=ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 src=Path(__file__).parent;files=list(src.glob('*.py'))+list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+[ROOT/'tools/chapter07_ranged_consumers'/n for n in ['policies_v1.py','mortar_box_v2.py']]+[ROOT/'tools/chapter07_strength_melee/policies_v2.py',ROOT/'tools/campaign_ordered_checkpoint.py'];modules=[ROOT/'packages/campaign/chapter07_ranged_consumers'/n for n in ['sotisp.module.v3.json','soticn.module.v4.json']]
 for p in modules:
  m=json.loads(p.read_bytes());files += [Path(p) for p in m['manifest']['metadata']['source_locks']];files.append(p)
 before={str(p):sha(p) for p in files};assert implementation_digest()=='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000';start=time.monotonic();code=pytest.main([str(src/n) for n in ['test_sotisp_guarded.py','test_soticn_guarded.py','test_motion_guarded.py']]+['-q']);after={str(p):sha(p) for p in files};assert before==after;out=ROOT/'validation/campaign/chapter07_3992_ranged_guards_v1/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();rep={'passed':code==0,'actual_exit':code,'elapsed':time.monotonic()-start,'core':implementation_digest(),'source_before':before,'source_after':after,'scope':'Original9source assertions plus2publicMotionGround→Fly in-flight with real orderedCP/head and live typedstate. No stage/client accuracy claim. Rawdefinitions unchanged from parent modules, metadata runtime version separately bound.','whole_stage_executed':False};out.write_text(json.dumps(rep,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':sha(out),'actual_exit':code}));raise SystemExit(code)
if __name__=='__main__':main()
