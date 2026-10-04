import json
from copy import deepcopy
from pathlib import Path
import pytest
from tools.chapter08_bsnake_combat.build_module_v1 import ROOT,OUT,OWNER,PROTECT,REBORN,D12,Compiler,providers,sha
from ark_sim import Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUTPROOF=ROOT/'validation/campaign/chapter08_bsnake_combat_author_v1'
INPUTS=[];CAPTURES=[]
def package(mode=0):
 assert sha(OUT)=='6ce843ab10eea77a0b116f3d9d40b395a003287b972550d6c6d2593bf9b2fbb5';p=json.loads(OUT.read_bytes());p['entities'][0]['components']['resources']['mode']['initial']=mode
 p['entities'].append({'id':'unit/test/bsnake/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100000,'atk':1000,'def':997,'mres':67,'block_count':0}},'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}})
 p['scenarioDraft']={'id':'scene/bsnake/combat/author','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':6},'objectives':{},'initialEntities':[{'definition':OWNER,'instanceAlias':'boss','position':{'row':1,'col':1}},{'definition':'unit/test/bsnake/player','instanceAlias':'player','position':{'row':1,'col':2}}]};return p
def make(p):
 INPUTS.append(deepcopy(p));reg=providers();pr=Compiler(providers=reg).compile(p,packages=[str(D12)]);return pr,Engine.create(pr,providers=reg,seed=8187),reg
def proof(pr,s,reg,name,split,end):
 s.advance(split);d=OUTPROOF/name;d.mkdir(parents=True,exist_ok=True);f=d/'checkpoint.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h),providers=reg);s.advance(end-split);r.advance(end-split);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=reg).checkpoint();(d/'evidence.json').write_text(json.dumps({'input':INPUTS[-1],'cp_sha':h,'checkpoint':s.checkpoint()},indent=2),encoding='utf8');CAPTURES.append({'case':name,'cp_sha':h});return s
def hits(s,ability=None,target=None):return [e for e in s.session.events if e['type']=='damage.accepted' and (ability is None or e['payload']['ability']==ability) and (target is None or e['payload']['target']==target)]

def test_mode0_true770_native31_and_liveDragonFire_source_CPP16_head():
 p=package();pr,s,reg=make(p);proof(pr,s,reg,'normal0',16,100);x=hits(s,'ability/ch8/bsnake/normal/phase0');assert [(e['time'],e['payload']['amount']) for e in x]==[(31,770)];assert [(e['time'],e['payload']['amount']) for e in hits(s,'buff/ch8/source/dragon_fire[damage]')]==[]
 rows=s.ctx.get('player',('buffs','instances'));assert {i['definition'] for i in rows}=={'buff/ch8/source/dragon_fire','buff/ch8/source/dragon_fire[damage]'};burn=[e for e in hits(s) if e['payload']['ability'] is None];assert [(e['time'],e['payload']['amount']) for e in burn]==[(61,56),(91,62)]
 assert s.ctx.entity('boss')['components']['attributes']['base']['atk']==770 and 'sp' not in s.ctx.get('boss',('resources',))

def test_liveASPD2_true31_frameceil16_unscaledDEF_RES():
 p=package();p['buffs'].append({'id':'buff/test/aspeed','kind':'buff','modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':1}]});p['entities'][0]['components']['buffs']['initial'].append('buff/test/aspeed');pr,s,reg=make(p);proof(pr,s,reg,'ASPD2',8,50);assert [(e['time'],e['payload']['amount']) for e in hits(s,'ability/ch8/bsnake/normal/phase0')]==[(16,770)]

def test_real_firstRebirth37500_75000_1155_and_newmode1_frame31():
 p=package();counter=json.loads((ROOT/'validation/campaign/chapter08_bsnake_rebirth_selfboost_counter_v1/report.json').read_bytes())['input'];cfg=deepcopy(counter['entities'][0]['components']['rebirth']);cfg['on_finish']=[{'op':'modify_resource','target':'source','resource':'mode','value':1}];cfg['reset_attack_clock']=True;p['entities'][0]['components']['rebirth']=cfg;p['buffs'].append(counter['buffs'][0]);p['rules'].append(next(r for r in counter['rules'] if r['id']=='rule/bsnake/source_restore'));p['entities'][1]['components']['abilities'].append('ability/test/killboss');p['abilities'].append({'id':'ability/test/killboss','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'instant_kill','target':2,'parameters':{'cause':'author_first_rebirth','skip_rebirth':False}}]},'timeline':[]});pr,s,reg=make(p);s.submit({'action':'skill','source':'player','ability':'ability/test/killboss'},at=1);proof(pr,s,reg,'rebirth1',75,200);assert s.ctx.resources.current('boss','hp')==37500 and s.ctx.resources.capacity('boss','hp')==75000 and s.ctx.attributes.values(2)['atk']==1155;assert [(e['time'],e['payload']['amount']) for e in hits(s,'ability/ch8/bsnake/normal/phase1')]==[(182,1155)];assert not hits(s,'ability/ch8/bsnake/normal/phase0')

@pytest.mark.parametrize('flag,value',[('target_free',True),('camouflage',True),('motion',2),('side',1),('category',4)])
def test_native_typed_current_eligibility_no_dummy_hit(flag,value):
 p=package();p['entities'][1]['components']['selection_state'][flag]=value;pr,s,reg=make(p);s.advance(50);assert not hits(s) and not [e for e in s.session.events if e['type']=='ability.started']

def protection_package():
 p=package(2);p['entities'][1]['components']['abilities']=['ability/test/'+t for t in ['physical','arts','true','burnself']]
 for t in ['physical','arts','true']:p['abilities'].append({'id':'ability/test/'+t,'kind':'ability','activation':{'mode':'manual','on_start':[{'op':'damage','target':2,'damage_type':t,'amount':1000,'damage_flags':{'source_attack_type':'SKILL','ignore_for_sp':False}}]},'timeline':[]})
 p['abilities'].append({'id':'ability/test/burnself','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'buff_application','target':'source','application_rule':'rule/ch8/dragon_fire/application','allowed':['buff/ch8/source/dragon_fire','buff/ch8/source/dragon_fire[damage]']}]},'timeline':[]});return p

def test_BSON_modifierSource_parent_live_all_types_half_expiry_not_child_CPP910_head():
 p=protection_package();pr,s,reg=make(p)
 for t,at in [('physical',0),('burnself',1),('physical',2),('arts',3),('true',4),('true',917)]:s.submit({'action':'skill','source':'player','ability':'ability/test/'+t},at=at)
 proof(pr,s,reg,'protection',910,930);assert [(e['time'],e['payload']['amount']) for e in hits(s,target=2)]==[(0,200),(2,100),(3,250),(4,500),(917,1000)];rows=s.ctx.get('player',('buffs','instances'));assert {i['definition'] for i in rows}=={'buff/ch8/source/dragon_fire[damage]'}
