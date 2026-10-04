import json
from copy import deepcopy
from tools.experiments.chapter06_boss_peer.test_revision_fixture import fixture,make,skill,ev,capture,ROOT,PREFIX
from tools.campaign_content_composition_v2 import compose_modules

def test_native_character_without_deployment_capability_not_ice_floor_candidate():
 p=fixture(initial={'ability_timing':{'initial_cooldowns':{PREFIX+'ice0':0}}});npc=json.loads((ROOT/'packages/campaign/chapter06_npcs/huang.v7.model.json').read_bytes());defs,_=compose_modules([('prior',p),('nativeCharacter',npc)]);p['definitions']=list(defs.values())
 # The one buildable candidate is the nativeCharacter tile. All other cells are source-declared nonbuildable; no actor/model fields altered.
 tiles=[{'tileKey':'tile_floor','buildableType':0,'passableMask':1,'heightType':0} for i in range(80)];tiles[2*10+3]['buildableType']=1;p['scenarioDraft']['map']['tiles']=tiles
 p['scenarioDraft']['initialEntities'].append({'definition':npc['entities'][0]['id'],'instanceAlias':'actual_huang','active':False,'registration_key':'char_017_huang','position':{'row':2,'col':3},'facing':'right'})
 p['definitions'].append({'id':'ability/peer/activate_npc','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'activate_predefined','target':'battle','parameters':{'key':'char_017_huang'}}]},'timeline':[]});next(d for d in p['definitions'] if d['id']=='unit/peer/controller')['components']['abilities'].append('ability/peer/activate_npc')
 s=make(p);s.submit({'action':'skill','source':'controller','ability':'ability/peer/activate_npc'},at=0);s.advance(61);capture(s,'NPC_character_tile_classification')
 assert s.ctx.entity('actual_huang')['components']['selection_state']['category']==1 and s.ctx.entity('actual_huang')['components']['selection_state']['unit_type']==1
 assert 'deployable' not in s.ctx.entity('actual_huang')['components']
 assert not [e for e in ev(s,'ability.started') if e['payload']['ability']==PREFIX+'ice0'] and s.ctx.active('actual_huang')

def test_original_normal_pointseven_fullbusy_expectation_unchanged_new_source():
 p=fixture(initial={'buffs':{'initial':['buff/unit/ch6/frstar2/3681c71c12a71fb0/sleepimmune','buff/ch6/cold/e2c_cold']},'ability_timing':{'initial_cooldowns':{PREFIX+'burst0':1.5}}});s=make(p)
 from tools.experiments.chapter06_boss_peer.test_revision_fixture import deploy
 deploy(s);s.advance(74);capture(s,'repaired_normal_fullbusy');normal=[e for e in ev(s,'ability.started') if e['payload']['ability']==PREFIX+'normal0'];burst=[e for e in ev(s,'ability.started') if e['payload']['ability']==PREFIX+'burst0'];assert normal and normal[0]['time']==0 and burst and burst[0]['time']>=69
