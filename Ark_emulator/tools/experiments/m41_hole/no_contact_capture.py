"""One real command scenario captured under an explicitly selected runtime."""
import json,sys
from pathlib import Path
runtime=Path(sys.argv[1]).resolve();sys.path.insert(0,str(runtime))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
p={'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/plain','kind':'entity','tags':['player'],
    'components':{'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'abilities':['ability/plain']}}],
    'abilities':[{'id':'ability/plain','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':2}}]},'timeline':[]}],
    'scenarioDraft':{'id':'scene/plain','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3},'initialEntities':[{'definition':'unit/plain','instanceAlias':'plain','position':{'row':0,'col':0}}]}}
program=Compiler().compile(p);s=Engine.create(program,seed=4131);s.submit({'action':'skill','source':'plain','ability':'ability/plain'},at=3);s.advance(20)
out={'module':sys.modules['ark_sim'].__file__,'core':implementation_digest(),'input':p,'snapshot':s.snapshot(),'checkpoint':s.checkpoint()}
Path(sys.argv[2]).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
