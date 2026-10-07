import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
out=ROOT/'validation/campaign/chapter0_stage_input_peer_v1';p=out/'source.review.v2.json';r=json.loads(p.read_bytes());assert r['source_input_approved'];assert all(sha(k)==v for k,v in r['current_source_guards'].items());assert implementation_digest()=='08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878'
compiled=[]
for row in r['results']:
 src=ROOT/'packages/campaign/chapter0_stage_models'/f"{row['stage']}.source.v2.json";program=Compiler().compile(json.loads(src.read_bytes()));compiled.append({'stage':row['stage'],'input_sha':sha(src),'program_fingerprint':program.fingerprint})
assert all(sha(k)==v for k,v in r['current_source_guards'].items())
receipt={'schema':'ark-sim/chapter0-stage-source-peer-freeze/v1','source_input_only_approved':True,'source_review_sha256':sha(p),'current_source_guards_before_after_equal':True,'compiled_default_core':implementation_digest(),'compiled':compiled,'whole_model_client_approved':False,'simulation_executed':False,'tools':{str(x):sha(x) for x in Path(__file__).parent.glob('*.py')},'prior_failure':'source.review.v1 preserved fixture assumption that reachOffset always zero; source00-11 actually has offsets. v2 compares complete raw route and explicit Cartesian row-sign policy, no source change.','pending':['Finite public plan static review once frozen','External ACK/prefix/whole actual evidence','Native UI/combat pause/dwell/render timing versus explicit logical-clock reference policy']}
dest=out/'final.freeze.v1.json';assert not dest.exists();dest.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps({'freeze_sha':sha(dest),'compiled':compiled}))
