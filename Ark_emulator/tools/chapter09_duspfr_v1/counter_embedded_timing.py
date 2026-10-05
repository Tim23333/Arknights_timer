import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str((ROOT/'../unpack_work/campaign_c9_duspfr_v1_candidate').resolve()));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_duspfr_v1.build import build,providers,BODY
p=build();p['scenarioDraft']={'id':'scene/timing-growth','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':3},'initialEntities':[{'definition':BODY,'instanceAlias':'source','position':{'row':1,'col':1}}]};s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers());s.ctx.resources.adjust('source','hp',value=0)
def count(value):
    if isinstance(value,dict):return int('depletion_timing_source' in value)+sum(count(x) for x in value.values())
    if isinstance(value,list):return sum(count(x) for x in value)
    return 0
rows=[]
for cast in s.ctx.get('source',('runtime','casts')).values():
    view=cast['depletion_timing_source'];rows.append({'ability':cast['ability'],'embedded_prior_proof_rows':count(view),'json_bytes':len(json.dumps(view))})
assert rows[-1]['embedded_prior_proof_rows']>rows[1]['embedded_prior_proof_rows']*2
r={'core':implementation_digest(),'actual_growth_reproduced':True,'rows':rows,'full_initial_author_run':'Interrupted before final report; not counted as passed','fix_direction':'Move full timing view to causal event; World stores event ID and pure restore comparison remains full'};(ROOT/'validation/campaign/chapter09_duspfr_v1/development.embedded_timing_growth.counter.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
