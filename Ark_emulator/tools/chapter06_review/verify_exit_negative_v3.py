"""Reject malformed exit math atomically and invalid content before execution."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_exit_accounting_v3_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay


def main():
    path=ROOT/'validation/campaign/exit_accounting_v3/probes/True.input.json';base=json.loads(path.read_bytes())
    core=implementation_digest();results=[]
    plans=[{'base_life_loss':True,'kills_delta':1,'leaks_delta':0},
           {'base_life_loss':-1,'kills_delta':1,'leaks_delta':0},
           {'base_life_loss':0,'kills_delta':True,'leaks_delta':0},
           {'base_life_loss':0,'kills_delta':1,'leaks_delta':1},
           {'base_life_loss':0,'kills_delta':1.0,'leaks_delta':0},
           {'base_life_loss':0,'kills_delta':1,'leaks_delta':0,'force_death':True}]
    for index,plan in enumerate(plans):
        p=deepcopy(base);p['rules'][0]['implementation']['expression']=repr(plan)
        sim=Engine.create(Compiler().compile(p),seed=662);sim.session.advance(1);before=sim.checkpoint()
        try:sim.ctx.lifecycle.exit('enemy')
        except ValueError:pass
        else:raise AssertionError(index)
        assert sim.checkpoint()==before
        results.append({'case':'invalid_plan_'+str(index),'rejected_atomically':True})
    for name,mutate in [('empty_rule',lambda p:p['entities'][0]['components']['lifecycle'].update(exit_rule='')),
                        ('bool_rule',lambda p:p['entities'][0]['components']['lifecycle'].update(exit_rule=True)),
                        ('list_parameters',lambda p:p['entities'][0]['components']['lifecycle'].update(exit_parameters=[])),
                        ('missing_rule_reference',lambda p:p['entities'][0]['components']['lifecycle'].update(exit_rule='rule/missing')),
                        ('wrong_contract',lambda p:p['rules'][0].update(contract='buff.duration'))]:
        p=deepcopy(base);mutate(p)
        try:Compiler().compile(p)
        except ValueError:pass
        else:raise AssertionError(name)
        results.append({'case':name,'compile_rejected':True})
    # Replaceable custom rule, without a hard-coded native flag branch.
    p=deepcopy(base);p['rules'][0]['implementation']['expression']="{'base_life_loss':4,'kills_delta':0,'leaks_delta':1}"
    sim=Engine.create(Compiler().compile(p),seed=662);sim.session.advance(51)
    assert sim.ctx.resources.current('system/battle','life')==99995 and sim.ctx.state()['leaks']==1
    assert sim.checkpoint()==replay(sim.program,sim.export_replay()).checkpoint()
    results.append({'case':'custom_formula_four_life','passed':True})
    assert implementation_digest()==core
    out=ROOT/'validation/campaign/exit_accounting_v3/negative.json';assert not out.exists()
    with out.open('x',encoding='utf8') as f:json.dump({'passed':True,'core':core,'cases':results,'source_input_sha':hashlib.sha256(path.read_bytes()).hexdigest(),
        'scope':'Author generic exit policy validation and replaceability; source native-body/whole-stage pending'},f,indent=2)
    print(json.dumps({'passed':True,'cases':len(results),'sha':hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
