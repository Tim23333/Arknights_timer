"""Public native NPC activation, true critical samples, disk restore/head proof."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter06_npcs.build_swllow import UID


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    core=implementation_digest();out=ROOT/'validation/campaign/chapter06_npc_swllow_v2';assert not out.exists();out.mkdir(parents=True)
    module=ROOT/'packages/campaign/chapter06_npcs/swllow.v2.model.json';p=json.loads(module.read_bytes())
    p['entities'].append({'id':'unit/npc_probe/receiver','kind':'entity','tags':['enemy','ground'],'components':{
        'attributes':{'base':{'max_hp':50000,'def':31,'mres':17}},'resources':{'hp':{'initial':50000,'capacity':50000,'role':'health'}},
        'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['entities'].append({'id':'unit/npc_probe/controller','kind':'entity','components':{'spatial':{},'abilities':['ability/npc_probe/activate']}})
    p['abilities'].append({'id':'ability/npc_probe/activate','kind':'ability','activation':{'mode':'manual','on_start':[
        {'op':'activate_predefined','target':'battle','parameters':{'key':'char_367_swllow'}}]},'timeline':[]})
    p['scenarioDraft']={'id':'scene/npc_probe/swllow','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'objectives':{},
        'parameters':{'deploy_capacity':0},'resources':{'dp':{'initial':0,'capacity':99},'life':{'initial':99999,'capacity':99999}},
        'initialEntities':[{'definition':UID,'active':False,'registration_key':'char_367_swllow','position':{'row':1,'col':1}},
            {'definition':'unit/npc_probe/receiver','instanceAlias':'receiver','position':{'row':1,'col':2}},
            {'definition':'unit/npc_probe/controller','instanceAlias':'controller','position':{'row':0,'col':0}}]}
    inp=out/'input.json';inp.write_text(json.dumps(p,indent=2)+'\n',encoding='utf8',newline='')
    program=Compiler().compile(p);sim=Engine.create(program,seed=61617)
    ref=sim.ctx.state()['predefined_registry']['char_367_swllow'];assert not sim.ctx.active(ref)
    sim.submit({'action':'skill','source':'controller','ability':'ability/npc_probe/activate'},at=10)
    sim.session.advance(11);assert sim.ctx.active(ref) and sim.ctx.state()['predefined_registry']['char_367_swllow']==ref
    assert sim.ctx.resources.current(ref,'hp')==1306 and 'sp' not in sim.ctx.get(ref,('resources',))
    assert sim.ctx.resources.current('system/battle','dp')==0
    cp=out/'activated.checkpoint.json';pin=write_ordered(cp,sim.checkpoint());r=Engine.restore(program,load_bound(cp,pin))
    sim.session.advance(889);r.session.advance(889);head=replay(program,sim.export_replay())
    assert sim.checkpoint()==r.checkpoint()==head.checkpoint()
    hits=[e for e in sim.session.events if e['type']=='damage.accepted' and e['payload']['source']==ref]
    requests=[e for e in sim.session.events if e['type']=='calculation' and e['payload']['rule_id']=='rule/ch6/npc/swllow_critical']
    assert hits and len(hits)==len(requests)
    expected=[]
    for req,event in zip(requests,hits):
        sample=req['payload']['trace']['inputs']['samples'];assert len(sample)==1
        damage=641 if sample[0]['value']<.15 else 417
        assert event['payload']['amount']==damage;expected.append(damage)
    assert {417,641}<=set(expected)
    assert len([e for e in sim.session.events if e['type']=='entity.activated' and e['payload']['target']==ref])==1
    assert not [e for e in sim.session.events if e['type']=='entity.deployed' and e['payload']['target']==ref]
    assert core==implementation_digest()
    replaypath=out/'replay.json';replaypath.write_text(json.dumps(sim.export_replay(),indent=2)+'\n',encoding='utf8',newline='')
    report={'passed':True,'core':core,'module_sha':sha(module),'input_sha':sha(inp),'checkpoint_sha':pin,'activation_tick':10,
        'actual_hits':[{'time':e['time'],'amount':e['payload']['amount']} for e in hits],'rng_samples_verified':len(requests),
        'same_native_id_activation':True,'public_deploy_count':0,'dp_unchanged':True,'no_selected_skill_or_sp':True,
        'full_checkpoint_equal':True,'head_equal':True,'events':len(sim.session.events),
        'scope':'Author Swallow NPC controlled activation and source crit/basic attack; three-part restart/priority/source-policy independent review and full stage pending'}
    target=out/'verification.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'passed':True,'hits':len(hits),'events':len(sim.session.events),'sha':sha(target)}))


if __name__=='__main__':main()
