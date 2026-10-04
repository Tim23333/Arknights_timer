"""Explicit external state effect must not initialize a dormant behavior."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.experiments.m20_peer import probe as h
import json
import hashlib
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
def case():
    p=h.fixture();p['entities'][0]['components']['behavior']={'machine':'behavior/latent'}
    p['behaviors']=[{'id':'behavior/latent','kind':'behavior','initial':'sleep','states':{
      'sleep':{},'awake':{'on_enter':[{'op':'emit','target':'source','event':'latent.awake_before_activation'}]}},'transitions':[]}]
    p['abilities'].append({'id':'ability/force_state','kind':'ability','activation':{'mode':'manual','on_start':[
        {'op':'state','target':2,'state':'awake'}]},'timeline':[]})
    p['entities'][1]['components']['abilities'].append('ability/force_state')
    s=h.make(p);h.command(s,'ability/force_state',1);s.advance(2)
    actual={'active':s.ctx.active(2),'state':s.ctx.get(2,('behavior','state')),'pre_activation_events':[thaw(e) for e in s.session.events if e['type']=='latent.awake_before_activation']}
    assert actual['state'] is None and not actual['pre_activation_events'],repr(actual)
if __name__=='__main__':
    start=implementation_digest()
    try:case();result={'result':'passed'}
    except Exception as e:result={'result':'failed','error':repr(e)}
    s=h.LAST
    result.update({'core_start':start,'core_completion':implementation_digest(),'runtime_module':h.ark_sim.__file__,
      'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'fixture_helper_sha256':hashlib.sha256(Path(h.__file__).read_bytes()).hexdigest(),
      'program':s.program.fingerprint,'commands':s.export_replay(),'initial':thaw(s.program.scenario),'snapshot':s.snapshot(),'events':[thaw(e) for e in s.session.events],
      'provisional':True,'formal_approval':False})
    out=h.ROOT/'validation/campaign/m20_dormant_peer_behavior_initial.json';out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k in ('result','error','core_start','core_completion')}))
