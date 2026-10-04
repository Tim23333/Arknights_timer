import json
from pathlib import Path
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter06_review.runner_providers_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_content_composition_v2 import compose_modules
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
def test_real_story95000_actorfree2000_cadence48_final1000_death_once_ordered_CP_head(tmp_path):
 boss=json.loads((ROOT/'packages/campaign/chapter06_boss/frstar2_s_v3/model.json').read_bytes());cold=json.loads((ROOT/'packages/campaign/chapter06_cold/model.json').read_bytes());defs,_=compose_modules([('nativeStory',boss),('nativeCold',cold)]);uid=boss['entities'][0]['id'];p={'schemaVersion':2,'manifest':{'id':'package/peer/storytimer','requires':['preset/ark_standard']},'definitions':list(defs.values()),'scenarioDraft':{'id':'scene/peer/storytimer','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1,'tiles':[{'tileKey':'tile_floor','buildableType':0,'passableMask':1}]},'objectives':{},'initialEntities':[{'definition':uid,'instanceAlias':'story','position':{'row':0,'col':0}}]}};INPUTS.append(deepcopy(p));r=providers();s=Engine.create(Compiler(providers=r).compile(p),providers=r);s.advance(31);assert s.ctx.resources.current('story','hp')==93000;cp=tmp_path/'story_real31.json';pin=write_ordered(cp,s.checkpoint());rest=Engine.restore(s.program,load_bound(cp,pin),providers=r);s.advance(1410);rest.advance(1410);head=replay(s.program,s.export_replay(),providers=r);CAPTURES.append({'case':'actualstorytimer','events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'saved_cp':str(cp),'saved_sha':pin});assert s.checkpoint()==rest.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==list(range(30,1441,30)) and [e['payload']['amount'] for e in hits]==[2000]*47+[1000]
 assert all(e['payload']['source'] is None and e['payload']['attack_type']=='BUFF' and e['payload']['damage_without_modify'] is True for e in hits)
 assert not s.ctx.alive('story') and len([e for e in s.session.events if e['type']=='combat.kill'])==1 and not s.ctx.get('story',('buffs','instances'),[]) and 'sp' not in s.ctx.get('story',('resources',))
