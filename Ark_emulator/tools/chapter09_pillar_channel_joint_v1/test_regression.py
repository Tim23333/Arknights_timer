"""Author compatibility reuse of own frozen primitive fixtures, on new core."""
import sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_pillar_channel_joint_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_depletion import test_depletion_v2 as base
from tools.chapter09_depletion import test_strict_v2 as strict
base.LOG=Path(__import__('os').environ['ARKSIM_RUN_DIR'])
def main():
    guard=implementation_digest();results=[]
    for fn in [base.exact_zero_ready_source,base.forged_callbacks_and_secondary_damage,base.atomic_late_fault,base.retire_cancels,base.cpp_head_tamper,base.resource_not_attack_and_nested_authority,strict.due_and_rehashed_time,strict.key_slot_done_stage,strict.direct_dispatch_and_incarnation,strict.source_request_plan_tamper]:
        try:fn();results.append({'case':fn.__name__,'passed':True})
        except Exception as error:results.append({'case':fn.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    base.cleanup();report={'core_before':guard,'core_after':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in results) else 1,'results':results,'scope':'Own primitive fixture regression on new bridge core, not independent peer','cleanup':base.CLEANUPS,'raw_deleted':all(not Path(x['path']).exists() for x in base.ARTIFACTS)}
    (ROOT/'validation/campaign/chapter09_pillar_channel_joint_v1/author.regression.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
