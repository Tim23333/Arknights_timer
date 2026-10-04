"""Exact native story/activation actions; explicit no-Boss controlled subset."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.adapters.api import implementation_digest
from tools.chapter06_npcs.amiya_policy import providers
from tools.campaign_content_composition import compose_modules
from tools.chapter06_review.story_keys_v5 import convert
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def main():
    nativepath=ROOT/'packages/campaign/chapter06_plans/source.plan.json';native=json.loads(nativepath.read_bytes())['stages']['level_main_06-15']['native_document']
    files=[ROOT/'packages/campaign/chapter06_npcs'/name for name in ['swllow.v2.model.json','huang.model.json','amiya.v3.model.json','story_controls.v2.model.json']]
    modules=[(f.name,json.loads(f.read_bytes())) for f in files];definitions,_=compose_modules(modules)
    native_keys=['char_002_amiya','char_017_huang','char_367_swllow'];bound={k:'unit/ch6/npc/'+k for k in native_keys}
    from tools.chapter06_review.story_keys_v5 import digest
    profile={'schema':'ark-sim/story-predefined-key-profile/v1','policy':'unique_native_character_key_for_hidden_null_alias',
        'native_id':'level_main_06-15','native_document_digest':digest(native),'bindings':[{'bucket':'characterInsts','index':i,
        'activation_key':raw['inst']['characterKey'],'definition':bound[raw['inst']['characterKey']]} for i,raw in enumerate(native['predefines']['characterInsts'])]}
    predefined=convert(native,'level_main_06-15',bound,story_key_profile=profile)
    story_controls={c['metadata']['native_story_key']:c for c in modules[-1][1]['controls']}
    waves=[]
    for wi,w in enumerate(native['waves']):
        fragments=[]
        for fi,f in enumerate(w['fragments']):
            actions=[]
            for ai,a in enumerate(f['actions']):
                if a['actionType']=='SPAWN':continue
                common={'count':a['count'],'delay_seconds':a['preDelay'],'interval_seconds':a['interval'],'managed':a['managedByScheduler'],
                    'blocks_wave':not a['dontBlockWave'],'blocks_fragment':a['blockFragment'],
                    'metadata':{'native_wave':wi,'native_fragment':fi,'native_action_index':ai,'native_action':deepcopy(a)}}
                if a['actionType']=='STORY':actions.append({'kind':'control','definition':story_controls[a['key']]['id'],**common})
                elif a['actionType']=='ACTIVATE_PREDEFINED':actions.append({'kind':'effects','effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':a['key']}}],**common,'managed':False,'blocks_wave':False,'blocks_fragment':False})
                else:raise ValueError('Unconverted control')
            fragments.append({'pre_delay_seconds':f['preDelay'],'actions':actions})
        waves.append({'pre_delay_seconds':w['preDelay'],'post_delay_seconds':w['postDelay'],'max_wait_seconds':w['maxTimeWaitingForNextWave'],'fragments':fragments})
    rows=len(native['mapData']['map']);cols=len(native['mapData']['map'][0])
    package={'schemaVersion':2,'definitions':list(definitions.values()),'scenarioDraft':{'id':'scene/ch6/native_control_subset','ruleset':'ruleset/ark_standard',
        'map':{'rows':rows,'cols':cols},'resources':{'dp':{'initial':0,'capacity':99}},'parameters':{'deploy_capacity':0},'objectives':{},
        'initialEntities':predefined['initial_entities'],'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':waves},
        'metadata':{'explicit_omission':'Only controls and native NPCs; sourceBoss birth/map mechanics deliberately not in this controlled subset. Not whole6-17.'}}}
    out=ROOT/'validation/campaign/chapter06_native_controls_subset_v2';assert not out.exists();out.mkdir(parents=True)
    (out/'input.json').write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(package),seed=61726,providers=reg);driver=PublicAckDriver(s);driver.advance_to(60)
    cp=out/'bundle.json';pin=write_ordered(cp,{'simulation':s.checkpoint(),'driver':driver.checkpoint()});loaded=load_bound(cp,pin)
    r=Engine.restore(s.program,loaded['simulation'],providers=reg);rd=PublicAckDriver(r,loaded['driver']);driver.advance_to(900);rd.advance_to(900)
    head=replay(s.program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==head.checkpoint() and driver.checkpoint()==rd.checkpoint()
    activation=[e for e in s.session.events if e['type']=='entity.activated'];assert len(activation)==3
    assert len(driver.submitted)==7 and len([e for e in s.session.events if e['type']=='control.completed'])==5
    times=[e['time'] for e in activation];assert times==[60,240,420],times
    assert not [e for e in s.session.events if e['type']=='entity.deployed'] and s.ctx.resources.current('system/battle','dp')==0
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'native_source_sha':hashlib.sha256(nativepath.read_bytes()).hexdigest(),
        'public_ack_count':7,'activation_ticks':times,'cp_sha':pin,'head_equal':True,'no_boss_or_fake_whole_claim':True,
        'scope':'Source control delays/fields all preserved and exact NPC hidden instances. NativeBoss/map/source global clock behavior must be joined and separately validated.'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest(),'activation_ticks':times}))


if __name__=='__main__':main()
