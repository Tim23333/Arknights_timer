"""True route exits and source-selected credit, durable CP and public replay."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_exit_accounting_v3_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    core=implementation_digest();assert core=='efad001ce0b34274301b417821e0d24df8abb14c956e4c7ef099ea74a1d95322'
    source=ROOT/'packages/campaign/chapter06_exit_accounting/reference_policy.json';policy=json.loads(source.read_bytes())
    out=ROOT/'validation/campaign/exit_accounting_v3/probes';assert not out.exists();out.mkdir(parents=True)
    results=[]
    for special in (False,True):
        lifecycle={'policy':'policy/ark_lifecycle','leak_loss':2}
        if special:lifecycle.update(deepcopy(policy['actionLifecycleProfile']['lifecycle']))
        data={'schemaVersion':2,'manifest':policy['manifest'],'rules':policy['rules'],'entities':[{'id':'unit/exit/probe','kind':'entity','tags':['enemy'],
            'components':{'attributes':{'base':{'max_hp':95000,'atk':0,'def':300,'mres':50,'move_speed':3,'block_cost':1}},
                'resources':{'hp':{'initial':95000,'capacity':95000,'role':'health'}},'spatial':{},'lifecycle':lifecycle}}],
            'scenarioDraft':{'id':'scene/exit/probe/'+str(special),'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},
                'resources':{'life':{'initial':99999,'capacity':99999}},'objectives':{'type':'waves','life_resource':'life'},
                'waves':[{'definition':'unit/exit/probe','instanceAlias':'enemy','position':{'row':0,'col':0},'route':{'motionMode':'WALK',
                    'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':2},'checkpoints':[]}}]}}
        inp=out/(str(special)+'.input.json');inp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8',newline='')
        program=Compiler().compile(data);sim=Engine.create(program,seed=6617);sim.session.advance(4)
        assert sim.ctx.resources.current('enemy','hp')==95000
        cp=out/(str(special)+'.checkpoint.json');pin=write_ordered(cp,sim.checkpoint());r=Engine.restore(program,load_bound(cp,pin))
        for s in (sim,r):s.session.advance(47)
        head=replay(program,sim.export_replay());assert sim.checkpoint()==r.checkpoint()==head.checkpoint()
        state=sim.ctx.state();assert state['finished'] and state['pending_waves']==0
        assert (state['kills'],state['leaks'])==((1,0) if special else (0,1))
        assert sim.ctx.resources.current('system/battle','life')==(99999 if special else 99997)
        assert sim.ctx.get('enemy',('runtime','state'))=='exited' and sim.ctx.resources.current('enemy','hp')==95000
        assert not any(e['type'] in ('entity.died','combat.kill') for e in sim.session.events)
        before=sim.checkpoint();sim.ctx.lifecycle.exit('enemy') if special else None
        assert sim.checkpoint()==before
        results.append({'special':special,'passed':True,'state':state,'checkpoint_sha':pin,'hp_preserved':95000,'real_state':'exited','input_sha':sha(inp)})
    assert core==implementation_digest()
    target=out/'verification.json'
    with target.open('x',encoding='utf8') as f:json.dump({'core':core,'passed':True,'results':results,'policy_sha':sha(source),
        'scope':'Explicit exit accounting only; combined source flag policy is replaceable, not whole6-17/Boss/NPC approval'},f,indent=2)
    print(json.dumps({'passed':True,'sha':sha(target)}))


if __name__=='__main__':main()
