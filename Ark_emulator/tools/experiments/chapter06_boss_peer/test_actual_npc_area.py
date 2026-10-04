import json
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_content_composition_v2 import compose_modules
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter06_review.runner_providers_v1 import providers
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
def fixture(source):
 folder='frstar2_v4' if source=='ordinary' else 'frstar2_s_v3';boss=json.loads((ROOT/'packages/campaign/chapter06_boss'/folder/'model.json').read_bytes());uid=boss['entities'][0]['id'];aid='ability/'+uid+('/burst0' if source=='ordinary' else '/burst');module_paths=['packages/campaign/chapter06_cold/model.json','packages/campaign/chapter06_npcs/amiya.v3.model.json','packages/campaign/chapter06_npcs/swllow.v2.model.json','packages/campaign/chapter06_npcs/huang.v7.model.json'];mods=[('selectedSource',boss)]+[(p,json.loads((ROOT/p).read_bytes())) for p in module_paths];native=json.loads((ROOT/'packages/campaign/chapter06_plans/source.plan.json').read_bytes())['stages']['level_main_06-15']['native_document'];initial=[{'definition':uid,'instanceAlias':'boss','position':{'row':3,'col':2},'components':{'ability_timing':{'initial_cooldowns':{aid:0}}}}];keys=[]
 for rec in native['predefines']['characterInsts']:
  key=rec['inst']['characterKey'];keys.append(key);initial.append({'definition':'unit/ch6/npc/'+key,'instanceAlias':key,'active':False,'registration_key':key,'position':{'row':6-rec['position']['row'],'col':rec['position']['col']},'facing':rec['direction'].lower(),'parameters':{'native_instance':deepcopy(rec)}})
 controller={'id':'unit/peer/controller','kind':'entity','components':{'abilities':['ability/peer/activate'],'spatial':{}}};activation={'id':'ability/peer/activate','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'activate_predefined','target':'battle','parameters':{'key':key}} for key in keys]},'timeline':[]};mods.append(('fresh',{'entities':[controller],'abilities':[activation]}));defs,_=compose_modules(mods);initial.append({'definition':controller['id'],'instanceAlias':'controller','position':{'row':6,'col':8}});scene={'id':'scene/independent/actualNPCburst/'+source,'ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':9},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':0,'capacity':99}},'parameters':{'deploy_capacity':0},'objectives':{},'initialEntities':initial}
 if source=='ordinary':
  trap=json.loads((ROOT/'packages/campaign/chapter06_predefines_consumer/module.v2.reference.json').read_bytes());defs,_=compose_modules([('combined',{'definitions':list(defs.values())}),('sourceTrap',trap)]);scene['branches']=deepcopy(trap['manifest']['metadata']['native_branch_programs']['level_main_06-14']);scene['initialEntities']+=deepcopy(trap['manifest']['metadata']['native_predefined_profiles']['level_main_06-14']['initial_entities'])
 return {'schemaVersion':2,'manifest':{'id':'package/peer/NPCburst','requires':['preset/ark_standard']},'definitions':list(defs.values()),'scenarioDraft':scene},aid,28 if source=='ordinary' else 87
@pytest.mark.parametrize('source',['ordinary','story'])
def test_three_original_native_NPC_one_area_one_packet_each_cold_once_actual_disk_head(source,tmp_path):
 p,aid,frame=fixture(source);INPUTS.append(deepcopy(p));r=providers();s=Engine.create(Compiler(providers=r).compile(p),providers=r,seed=6073);s.submit({'action':'skill','source':'controller','ability':'ability/peer/activate'},at=0);s.advance(frame-1);path=tmp_path/'real_NPC_preBurst.json';pin=write_ordered(path,s.checkpoint());rest=Engine.restore(s.program,load_bound(path,pin),providers=r);s.advance(3);rest.advance(3);head=replay(s.program,s.export_replay(),providers=r);CAPTURES.append({'case':source,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'saved_cp':str(path),'saved_sha':pin});assert s.checkpoint()==rest.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
 areas=[e for e in s.session.events if e['type']=='area.resolved' and e['payload']['source']==2];hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['ability']==aid];assert len(areas)==1 and len(hits)==3 and sorted(e['payload']['amount'] for e in hits)==pytest.approx([352,440,440] if source=='ordinary' else [960,1200,1200])
 for key in ['char_002_amiya','char_367_swllow','char_017_huang']:
  buffs=s.ctx.get(key,('buffs','instances'),[]);cold=[b for b in buffs if b['definition']=='buff/ch6/cold/e2c_cold'];assert len(cold)==1 and cold[0]['expires_at']==frame+300 and not any(b['definition']=='buff/ch6/cold/e2c_freeze' for b in buffs)
 assert not [e for e in s.session.events if e['type']=='command.rejected'] and p['scenarioDraft']['parameters']['deploy_capacity']==0
