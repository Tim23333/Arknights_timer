import sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_pillar_channel_joint_v3_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_depletion import test_depletion_v2 as base
sys.modules['test_depletion_v2']=base
from tools.chapter09_depletion import test_context_v2 as contexts
before=implementation_digest();results=[]
for fn in [contexts.custom_context_clock_cpp_head,contexts.legacy_no_optin]:
    try:fn();results.append({'case':fn.__name__,'passed':True})
    except Exception as error:results.append({'case':fn.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
report={'core_before':before,'core_after':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in results) else 1,'results':results,'scope':'Fresh own custom context/clock and legacy fixture regression on new lease-restoration core; not independent peer'}
(ROOT/'validation/campaign/chapter09_pillar_channel_joint_v3/author.context.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report));raise SystemExit(report['actual_exit'])
