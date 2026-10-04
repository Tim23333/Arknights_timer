"""Actual hidden NPC becomes one actor; normal ten-frame hits three ground foes."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter06_npcs.policies import providers


def main():
    source=ROOT/'packages/campaign/chapter06_npcs/huang.model.json';p=json.loads(source.read_bytes())
    p['entities'].append({'id':'unit/npc_probe/foe','kind':'entity','tags':['enemy','ground'],'components':{
        'attributes':{'base':{'max_hp':10000,'def':31,'mres':17,'block_cost':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'spatial':{},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['entities'].append({'id':'unit/npc_probe/controller','kind':'entity','components':{'spatial':{},'abilities':['ability/npc_probe/activate_huang']}})
    p['abilities'].append({'id':'ability/npc_probe/activate_huang','kind':'ability','activation':{'mode':'manual','on_start':[
        {'op':'activate_predefined','target':'battle','parameters':{'key':'char_017_huang'}}]},'timeline':[]})
    p['scenarioDraft']={'id':'scene/npc_probe/huang_three','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':4},'objectives':{},
        'parameters':{'deploy_capacity':0},'resources':{'dp':{'initial':0,'capacity':99}},'initialEntities':[
            {'definition':'unit/ch6/npc/char_017_huang','active':False,'registration_key':'char_017_huang','position':{'row':1,'col':1}},
            *[{'definition':'unit/npc_probe/foe','instanceAlias':'foe'+str(i),'position':{'row':1,'col':2}} for i in range(4)],
            {'definition':'unit/npc_probe/controller','instanceAlias':'controller','position':{'row':0,'col':0}}]}
    out=ROOT/'validation/campaign/chapter06_npc_huang_attack_v1';assert not out.exists();out.mkdir(parents=True)
    (out/'input.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf8',newline='')
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),seed=61721,providers=reg);ref=s.ctx.state()['predefined_registry']['char_017_huang']
    s.submit({'action':'skill','source':'controller','ability':'ability/npc_probe/activate_huang'},at=5);s.session.advance(6)
    assert s.ctx.active(ref) and 'sp' not in s.ctx.get(ref,('resources',))
    cp=out/'activated.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg)
    s.session.advance(12);r.session.advance(12);head=replay(s.program,s.export_replay(),providers=reg)
    assert s.checkpoint()==r.checkpoint()==head.checkpoint()
    hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==ref]
    assert len(hits)==3 and all(e['time']==15 and e['payload']['amount']==600 for e in hits)
    assert len({e['payload']['target'] for e in hits})==3
    assert s.ctx.resources.current('foe3','hp')==10000
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'module_sha':hashlib.sha256(source.read_bytes()).hexdigest(),
        'cp_sha':pin,'activation':5,'hit_frame':15,'damage600_targets':3,'fourth_untouched':True,'no_skill_or_sp':True,'head_equal':True,
        'scope':'Author native Blaze normal trait/hidden activation on self-remove candidate; independent target priority/talent/all-native-stage pending'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
