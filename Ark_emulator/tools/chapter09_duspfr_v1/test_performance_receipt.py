import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str((ROOT/'../unpack_work/campaign_c9_duspfr_v1_candidate').resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from tools.chapter09_duspfr_v1.build import build,providers,BODY
before=implementation_digest();p=build();p['scenarioDraft']={'id':'scene/timing-reference','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':3},'initialEntities':[{'definition':BODY,'instanceAlias':'source','position':{'row':1,'col':1}}]};s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers());started=time.perf_counter();s.ctx.resources.adjust('source','hp',value=0);elapsed=time.perf_counter()-started
rows=[]
for cast in s.ctx.get('source',('runtime','casts')).values():
    assert 'depletion_timing_source' not in cast;event=s.session.events[cast['depletion_timing_source_event']-1];assert event['type']=='depletion.cast.timing_source'
    rows.append({'ability':cast['ability'],'world_proof_reference_type':type(cast['depletion_timing_source_event']).__name__,'full_timing_source_json_bytes':len(json.dumps(thaw(event['payload']['view']))),'world_cast_json_bytes':len(json.dumps(cast))})
assert len(rows)==5 and rows[-1]['full_timing_source_json_bytes']<100000
r={'core_before':before,'core_after':implementation_digest(),'actual_exit':0,'rows':rows,'actual_parallel_start_wall_seconds':elapsed,'world_entity_json_bytes':len(json.dumps(thaw(s.session.world.get('source')))),'old_counter':'development.embedded_timing_growth.counter.json','comparison_scope':'Same5 child startup shape; old cast5 had53 embedded prior proof copies/537854-byte timing view. New World uses integer event references; full view remains in causal event and is validated. Not full stage throughput claim.'};(ROOT/'validation/campaign/chapter09_duspfr_v1/author.performance.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
