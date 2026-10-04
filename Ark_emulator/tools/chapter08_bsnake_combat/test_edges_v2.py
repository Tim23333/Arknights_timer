from copy import deepcopy
import pytest
from tools.chapter08_bsnake_combat.test_source_v3 import package,make,proof,hits,protection_package
from tools.chapter08_bsnake_combat.build_module_v2 import PROTECT,REBORN

def test_actual_blocker_identity_beats_1e9_taunt_unblocked_candidate():
 p=package();p['entities'][1]['components']['attributes']['base']['taunt_level']=1e9;blocker=deepcopy(p['entities'][1]);blocker['id']='unit/test/actualblocker';blocker['components']['attributes']['base'].update(block_count=1,taunt_level=0);blocker['components']['deployable']={'base_cost':7,'capacity':1,'terrain':'ground','cooldown_seconds':0};p['entities'].append(blocker);scene=p['scenarioDraft'];scene['roster']=[blocker['id']];scene['resources']={'dp':{'initial':10,'capacity':99}};scene['initialEntities'][0]['route']={'motionMode':'WALK','startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':5},'checkpoints':[]};pr,s,reg=make(p);s.submit({'action':'deploy','definition':blocker['id'],'alias':'blocker','position':{'row':1,'col':1}},at=0);proof(pr,s,reg,'blocked_identity',15,70);x=hits(s,'ability/ch8/bsnake/normal/phase0');assert len(x)==1 and x[0]['payload']['target']==s.session.world.resolve('blocker') and x[0]['payload']['amount']==770;assert s.ctx.resources.current('player','hp')==100000

@pytest.mark.parametrize('distance,accepted',[(2,True),(2.0000001,False)])
def test_closed_native_DB_radius2_boundary(distance,accepted):
 p=package();p['scenarioDraft']['initialEntities'][1]['position']['col']=1+distance;pr,s,reg=make(p);s.advance(50);assert bool(hits(s,'ability/ch8/bsnake/normal/phase0')) is accepted

def test_live_source_ATK_modifier_hits870_true_ignores_live_DEF_RES_CPP15():
 p=package();p['buffs'].append({'id':'buff/test/atkplus100','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':100}]});p['entities'][1]['components']['abilities']=['ability/test/boostBoss'];p['abilities'].append({'id':'ability/test/boostBoss','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':2,'buff':'buff/test/atkplus100'}]},'timeline':[]});pr,s,reg=make(p);s.submit({'action':'skill','source':'player','ability':'ability/test/boostBoss'},at=10);proof(pr,s,reg,'live_attack',15,50);assert [(e['time'],e['payload']['amount']) for e in hits(s,'ability/ch8/bsnake/normal/phase0')]==[(31,870)];assert s.ctx.entity('boss')['components']['attributes']['base']['atk']==770

def test_public_target_withdraw_before31_no_damage_no_burn():
 p=package();p['entities'][1]['components']['abilities']=['ability/test/withdraw'];p['abilities'].append({'id':'ability/test/withdraw','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}]},'timeline':[]});pr,s,reg=make(p);s.submit({'action':'skill','source':'player','ability':'ability/test/withdraw'},at=15);proof(pr,s,reg,'target_withdraw',10,50);assert not hits(s) and not [e for e in s.session.events if e['type']=='buff.applied' and e['payload']['target']==3]

def test_rebirth_protect_silenceable_custom_container_but_realBoss_immune12_preserved():
 # A distinct non-Boss container validates the reused content rule without rewriting source Boss immunities.
 p=protection_package();p['entities'][0]['id']='unit/test/unimmune_container';p['entities'][0]['metadata']={'fixture':'generic nonBoss owner, not native variant'};p['entities'][0]['components']['selection_state']['abnormal_immunes']=[];p['entities'][0]['components']['buffs']['initial']=[REBORN];p['scenarioDraft']['initialEntities'][0]['definition']=p['entities'][0]['id'];p['buffs'].append({'id':'buff/test/silence','kind':'buff','duration_seconds':1,'selection_flags':{'abnormal_flags':[12]}});p['entities'][1]['components']['abilities'].append('ability/test/silence');p['abilities'].append({'id':'ability/test/silence','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':2,'buff':'buff/test/silence'}]},'timeline':[]});pr,s,reg=make(p)
 for ability,at in [('burnself',0),('true',1),('silence',10),('true',11),('true',42)]:s.submit({'action':'skill','source':'player','ability':'ability/test/'+ability},at=at)
 proof(pr,s,reg,'silence_profile',12,50);assert [(e['time'],e['payload']['amount']) for e in hits(s,target=2)]==[(1,500),(11,1000),(42,500)]
 p=protection_package();p['entities'][0]['components']['buffs']['initial']=[REBORN];p['buffs'].append({'id':'buff/test/silence','kind':'buff','duration_seconds':1,'selection_flags':{'abnormal_flags':[12]}});p['entities'][1]['components']['abilities'].append('ability/test/silence');p['abilities'].append({'id':'ability/test/silence','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':2,'buff':'buff/test/silence'}]},'timeline':[]});pr,s,reg=make(p)
 for ability,at in [('burnself',0),('silence',10),('true',11)]:s.submit({'action':'skill','source':'player','ability':'ability/test/'+ability},at=at)
 proof(pr,s,reg,'Boss_native_silence_immune',12,50);assert [e['payload']['amount'] for e in hits(s,target=2)]==[500];assert 12 in s.ctx.entity('boss')['components']['selection_state']['abnormal_immunes']
