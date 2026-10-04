"""Valid graph implementation with invalid trajectory result must fail launch."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.experiments.m17_peer import probe as h
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
import json
import hashlib
def missing_reached(inputs,params,context):
    return {'position':dict(inputs['positions'][0]['position']),'motion_state':{}}
missing_reached.version='independent-adversarial-trajectory-result-v1'
def case():
    p=h.scene();p['rules'].append({'id':'rule/peer_missing_reached','kind':'calculation_rule','contract':'projectile.trajectory',
      'implementation':{'type':'provider','provider':'peer.missing_reached'}})
    p['projectiles'][1]['motion']['rule']='rule/peer_missing_reached'
    providers={**BUILTIN_PROVIDERS,'peer.missing_reached':missing_reached}
    s=Engine.create(Compiler(providers=providers).compile(p),seed=1717,providers=providers);h.LAST=s
    before=s.checkpoint();ability=thaw(s.program.definitions['ability/chapter01_w_c4_0'])
    try:s.ctx.projectiles.launch('w','target0',ability['timeline'][0]['effect'],ability,{},None)
    except ValueError:assert s.checkpoint()==before;return
    state=s.ctx.get('system/battle',('projectiles',));pending=[t for t in s.session.scheduler.pending if t['kind'].startswith('domain.projectile.')]
    raise AssertionError('missing reached was accepted at launch, active_instances='+str(len(state['instances']))+', jobs='+str(len(pending)))
if __name__=='__main__':
    start=implementation_digest()
    try:case();v={'result':'passed'}
    except Exception as e:v={'result':'failed','error':repr(e)}
    s=h.LAST;v.update({'core_start':start,'core_completion':implementation_digest(),'runtime_module':h.ark_sim.__file__,
      'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'actual_files_before_decode':h.LOADED,'program':s.program.fingerprint,
      'initial_scenario':thaw(s.program.scenario),'snapshot':s.snapshot(),'events':[thaw(e) for e in s.session.events],
      'API_only':True,'formal_approval':False})
    out=h.ROOT/'validation/campaign/m17_trajectory_result_initial.json';out.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v[k] for k in ('result','error','core_start','core_completion') if k in v}))
