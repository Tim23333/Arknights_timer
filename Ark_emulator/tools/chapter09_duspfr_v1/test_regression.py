import sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_duspfr_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_depletion import test_depletion_v2 as base
from tools.chapter09_depletion import test_strict_v2 as strict
sys.modules['test_depletion_v2']=base
from tools.chapter09_depletion import test_context_v2 as contexts
base.LOG=Path('E:/ArkSimLogs/runs/chapter09_duspfr_regression_v1')
def no_optin_graph():
    original=base.sim
    def graph_sim(d=None):
        for rule in (d or {}).get('rules',[]):
            if rule.get('contract')=='damage.pipeline' and rule['implementation']['type']=='expression':
                expr=rule['implementation']['expression'];rule['implementation']={'type':'graph','nodes':[{'id':'settle','expression':expr}],'output':'nodes.settle'}
        return original(d)
    base.sim=graph_sim
    try:contexts.legacy_no_optin()
    finally:base.sim=original
def main():
    before=implementation_digest();results=[]
    for fn in [base.exact_zero_ready_source,base.forged_callbacks_and_secondary_damage,base.atomic_late_fault,base.retire_cancels,base.cpp_head_tamper,base.resource_not_attack_and_nested_authority,strict.due_and_rehashed_time,strict.key_slot_done_stage,strict.direct_dispatch_and_incarnation,strict.source_request_plan_tamper,contexts.custom_context_clock_cpp_head,no_optin_graph]:
        try:fn();results.append({'case':fn.__name__,'passed':True})
        except Exception as error:results.append({'case':fn.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    base.cleanup();r={'core_before':before,'core_after':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in results) else 1,'results':results,'scope':'Fresh author regression on new core; original own zero6/strict4/customgraph1. Legacy NoSource pure formula represented as a graph to satisfy current107catalog; no core contract relaxed. Not independent peer.','cleanup':base.CLEANUPS,'raw_deleted':all(not Path(x['path']).exists() for x in base.ARTIFACTS)};(ROOT/'validation/campaign/chapter09_duspfr_v1/author.regression.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r));return r['actual_exit']
if __name__=='__main__':raise SystemExit(main())
