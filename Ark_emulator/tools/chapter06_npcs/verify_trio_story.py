"""Three true hidden no-skill NPCs and all source story rows, still a controlled chain."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_content_composition import compose_modules
from tools.chapter06_npcs.amiya_policy import providers
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def main():
    paths=[ROOT/'packages/campaign/chapter06_npcs'/name for name in ['swllow.v2.model.json','huang.model.json','amiya.v3.model.json','story_controls.v2.model.json']]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};parts=[(p.name,json.loads(p.read_bytes())) for p in paths]
    defs,_=compose_modules(parts);story=parts[-1][1]
    initial=[{'definition':'unit/ch6/npc/'+cid,'registration_key':cid,'active':False,'position':{'row':1,'col':index+1}}
        for index,cid in enumerate(['char_002_amiya','char_017_huang','char_367_swllow'])]
    fragments=[]
    for index,control in enumerate(story['controls']):
        actions=[{'kind':'control','definition':control['id'],'managed':True,'blocks_wave':True,'blocks_fragment':True}]
        if index<3:actions.append({'kind':'effects','delay_seconds':.1,'effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':initial[index]['registration_key']}}]})
        fragments.append({'actions':actions})
    data={'schemaVersion':2,'definitions':list(defs.values()),'scenarioDraft':{'id':'scene/ch6/npc_trio_story_controlled','ruleset':'ruleset/ark_standard',
        'map':{'rows':3,'cols':6},'resources':{'dp':{'initial':0,'capacity':99},'life':{'initial':99999,'capacity':99999}},
        'parameters':{'deploy_capacity':0},'objectives':{},'initialEntities':initial,
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':fragments}]}}}
    out=ROOT/'validation/campaign/chapter06_npc_trio_story_v1';assert not out.exists();out.mkdir(parents=True)
    (out/'input.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8',newline='')
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(data),seed=61725,providers=reg);driver=PublicAckDriver(s);driver.advance_to(1)
    cp=out/'bundle.json';pin=write_ordered(cp,{'simulation':s.checkpoint(),'driver':driver.checkpoint()});loaded=load_bound(cp,pin)
    r=Engine.restore(s.program,loaded['simulation'],providers=reg);rd=PublicAckDriver(r,loaded['driver'])
    driver.advance_to(40);rd.advance_to(40);head=replay(s.program,s.export_replay(),providers=reg)
    assert s.checkpoint()==r.checkpoint()==head.checkpoint() and driver.checkpoint()==rd.checkpoint()
    assert len(driver.submitted)==7 and len([e for e in s.session.events if e['type']=='control.completed'])==5
    registry=s.ctx.state()['predefined_registry']
    for cid,hp in [('char_002_amiya',1284),('char_017_huang',2305),('char_367_swllow',1306)]:
        ref=registry[cid];assert s.ctx.active(ref) and s.ctx.resources.current(ref,'hp')==hp and 'sp' not in s.ctx.get(ref,('resources',))
    assert len([e for e in s.session.events if e['type']=='entity.activated'])==3
    assert not [e for e in s.session.events if e['type']=='entity.deployed'] and s.ctx.resources.current('system/battle','dp')==0
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'source_pins':before,'cp_sha':pin,
        'native_npc_activations':3,'fixed12_actual_deployments':0,'stories':5,'dialogues':7,'head_equal':True,
        'scope':'Controlled source-NPC/story combination at declaredlogicaltiming, actualnative1/7/13sec schedule/Boss/map/whole6-17 still pending'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
