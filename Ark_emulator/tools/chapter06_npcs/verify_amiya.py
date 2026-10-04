"""Actual native hidden activation, one action-bearing arts packet, no fake SP."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter06_npcs.amiya_policy import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def main():
    path=ROOT/'packages/campaign/chapter06_npcs/amiya.v3.model.json';p=json.loads(path.read_bytes())
    p['entities']+=[{'id':'unit/npc_probe/amiya_target','kind':'entity','tags':['enemy','ground'],'components':{
        'attributes':{'base':{'max_hp':10000,'def':31,'mres':25}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'spatial':{},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'lifecycle':{'policy':'policy/ark_lifecycle'}}},
        {'id':'unit/npc_probe/amiya_controller','kind':'entity','components':{'spatial':{},'abilities':['ability/npc_probe/activate_amiya']}}]
    p['abilities'].append({'id':'ability/npc_probe/activate_amiya','kind':'ability','activation':{'mode':'manual','on_start':[
        {'op':'activate_predefined','target':'battle','parameters':{'key':'char_002_amiya'}}]},'timeline':[]})
    p['scenarioDraft']={'id':'scene/npc_probe/amiya','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'objectives':{},
        'parameters':{'deploy_capacity':0},'resources':{'dp':{'initial':0,'capacity':99}},'initialEntities':[
            {'definition':'unit/ch6/npc/char_002_amiya','active':False,'registration_key':'char_002_amiya','position':{'row':1,'col':1}},
            {'definition':'unit/npc_probe/amiya_target','instanceAlias':'target','position':{'row':1,'col':2}},
            {'definition':'unit/npc_probe/amiya_controller','instanceAlias':'controller','position':{'row':0,'col':0}}]}
    out=ROOT/'validation/campaign/chapter06_npc_amiya_v1';assert not out.exists();out.mkdir(parents=True)
    (out/'input.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf8',newline='')
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),seed=61722,providers=reg)
    s.submit({'action':'skill','source':'controller','ability':'ability/npc_probe/activate_amiya'},at=5);s.session.advance(6)
    ref=s.ctx.state()['predefined_registry']['char_002_amiya'];assert s.ctx.active(ref) and s.ctx.resources.current(ref,'hp')==1284
    cp=out/'activated.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg)
    s.session.advance(39);r.session.advance(39);head=replay(s.program,s.export_replay(),providers=reg)
    assert s.checkpoint()==r.checkpoint()==head.checkpoint()
    hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==ref]
    assert len(hits)==1 and hits[0]['payload']['amount']==408
    assert 'sp' not in s.ctx.get(ref,('resources',)) and s.ctx.resources.current('system/battle','dp')==0
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'module_sha':hashlib.sha256(path.read_bytes()).hexdigest(),
        'cp_sha':pin,'single_action_packet':1,'actual_arts_damage':408,'actual_hit_tick':hits[0]['time'],'no_fabricated_sp':True,'head_equal':True,
        'scope':'Author E2L25/no-skill Amiya controlled activation. Two emptyvisual dependencies kept; two-stage motion/firstbegin are explicitreference, nativecurvature/FSM handoff/complete-stage pending'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'hit':hits[0]['time'],'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
