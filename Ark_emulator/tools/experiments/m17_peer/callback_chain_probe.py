"""An explicit new projectile reference in on_invalid must not become instant damage."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.experiments.m17_peer import probe as h
from copy import deepcopy
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
import json,hashlib
def case():
    p=h.scene();child=deepcopy(p['projectiles'][1]);child.update(id='projectile/peer_child',lifetime_seconds=.2,on_invalid=[])
    p['projectiles'].append(child)
    p['projectiles'][1]['on_invalid']=[{'op':'damage','damage_type':'physical','scale':1,'projectile_definition':child['id']}]
    s=h.make(p);s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0);s.advance(115)
    launches=[thaw(x) for x in s.session.events if x['type']=='projectile.launched']
    hits=[thaw(x) for x in s.session.events if x['type']=='damage.accepted']
    actual={'launches':[(x['time'],x['payload'].get('definition')) for x in launches],
      'hits':[(x['time'],x['payload']['amount']) for x in hits],'target_HP':s.ctx.resources.current('target0','hp')}
    assert len(launches)==2 and launches[1]['payload']['definition']==child['id'] and launches[1]['time']==114,repr(actual)
    assert actual['target_HP']==4254 # child is born114/expires120, not an instant packet114
    assert next(iter(s.ctx.get('w',('runtime','casts')).values()))['pending_projectiles']==1
    s.advance(6);assert s.ctx.resources.current('target0','hp')==3884 and not s.ctx.get('w',('runtime','casts'))
    h.roundtrip(s)
if __name__=='__main__':
    core=implementation_digest()
    try:case();v={'result':'passed'}
    except Exception as e:v={'result':'failed','error':repr(e)}
    s=h.LAST;v.update({'core_start':core,'core_end':implementation_digest(),'runtime_module':h.ark_sim.__file__,
      'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'input_package_sha256':h.PIN,
      'program':s.program.fingerprint,'initial_scenario':thaw(s.program.scenario),'commands':s.export_replay(),
      'snapshot':s.snapshot(),'events':[thaw(x) for x in s.session.events],'formal_approval':False,
      'scope':'generic explicit on_invalid projectile definition; not a native W callback claim'})
    out=h.ROOT/'validation/campaign/m17_callback_chain_initial.json';out.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v[k] for k in ('result','error','core_start','core_end') if k in v}))
