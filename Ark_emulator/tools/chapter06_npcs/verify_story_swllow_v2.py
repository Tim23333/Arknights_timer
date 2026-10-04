"""Real five-story source chain with same native NPC activation and public ack."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_content_composition import compose_modules
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter06_npcs.build_swllow import UID


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out=ROOT/'validation/campaign/chapter06_story_swllow_v2';assert not out.exists();out.mkdir(parents=True)
    storypath=ROOT/'packages/campaign/chapter06_npcs/story_controls.v2.model.json';npcpath=ROOT/'packages/campaign/chapter06_npcs/swllow.model.json'
    story=json.loads(storypath.read_bytes());npc=json.loads(npcpath.read_bytes());defs,_=compose_modules([('actual_story',story),('actual_npc',npc)])
    actions=[{'kind':'control','definition':c['id'],'managed':True,'blocks_fragment':True,'blocks_wave':True} for c in story['controls']]
    fragments=[{'actions':[a]} for a in actions]
    fragments[0]['actions'].append({'kind':'effects','delay_seconds':.1,'effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':'char_367_swllow'}}]})
    package={'schemaVersion':2,'definitions':list(defs.values()),'scenarioDraft':{'id':'scene/ch6/story_npc_public_chain',
        'ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'parameters':{'deploy_capacity':0},'resources':{'dp':{'initial':0,'capacity':99}},'objectives':{},
        'initialEntities':[{'definition':UID,'registration_key':'char_367_swllow','active':False,'position':{'row':1,'col':1}}],
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':fragments}]}}}
    inp=out/'input.json';inp.write_text(json.dumps(package,indent=2)+'\n',encoding='utf8',newline='')
    core=implementation_digest();sim=Engine.create(Compiler().compile(package),seed=61618);driver=PublicAckDriver(sim);driver.advance_to(1)
    cp=out/'ordered.bundle.json';pin=write_ordered(cp,{'simulation':sim.checkpoint(),'driver':driver.checkpoint()});loaded=load_bound(cp,pin)
    continued=Engine.restore(sim.program,loaded['simulation']);peer=PublicAckDriver(continued,loaded['driver'])
    driver.advance_to(40);peer.advance_to(40);head=replay(sim.program,sim.export_replay())
    assert sim.checkpoint()==continued.checkpoint()==head.checkpoint() and driver.checkpoint()==peer.checkpoint()
    rows=[e for e in sim.session.events if e['type']=='source.story.row'];assert len(rows)==len(story['manifest']['metadata']['source_rows'])
    assert [e['payload']['raw_utf8'] for e in rows]==[r['raw_utf8'] for r in story['manifest']['metadata']['source_rows']]
    assert len(driver.submitted)==7 and len([e for e in sim.session.events if e['type']=='control.completed'])==5
    ref=sim.ctx.state()['predefined_registry']['char_367_swllow'];assert sim.ctx.active(ref) and sim.ctx.resources.current(ref,'hp')==1306
    assert len([e for e in sim.session.events if e['type']=='entity.activated' and e['payload']['target']==ref])==1
    assert not sim.ctx.state()['input_locks'] and sim.ctx.resources.current('system/battle','dp')==0
    assert core==implementation_digest()
    p=out/'verification.json'
    with p.open('x',encoding='utf8') as f:json.dump({'passed':True,'core':core,'story_sha':sha(storypath),'npc_sha':sha(npcpath),
        'bundle_sha':pin,'ack_count':7,'completed_story_count':5,'events':len(sim.session.events),'same_id_native_activation':True,
        'head_equal':True,'driver_state_equal':True,'scope':'Actual five payloads and Swallow controlled activation; timing is explicit logical profile, no full native6-17/NPC trio approval'},f,indent=2)
    print(json.dumps({'passed':True,'sha':sha(p),'events':len(sim.session.events)}))


if __name__=='__main__':main()
