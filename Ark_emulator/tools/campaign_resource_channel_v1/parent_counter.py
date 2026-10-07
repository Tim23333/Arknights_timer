import sys,os,json,hashlib,traceback
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_elemental_lease_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_resource_channel_v1.fixture import package
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_resource_channel_v1';FACT={};RESULT=[];ART=[];REG=BUILTIN_PROVIDERS

def create(p):return Engine.create(Compiler().compile(p),providers=REG,seed=23177491)
try:create(package())
except Exception as e:
 r={'core':implementation_digest(),'compile_rejected':True,'error':str(e),'source_native_counter_SHA':hashlib.sha256((ROOT/'validation/campaign/chapter10_stage17_ordinary_v1/dmech.channel.counter.v1.json').read_bytes()).hexdigest()};assert 'Owned attachment' in str(e)
else:raise AssertionError('Frozen parent unexpectedly accepted resource channel')
(OUT/'parent.counter.v1.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
