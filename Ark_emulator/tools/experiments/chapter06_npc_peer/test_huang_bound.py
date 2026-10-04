import json
from copy import deepcopy
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from tools.chapter06_npcs.policies import providers
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
def fixture(buff=None):
 p=json.loads((ROOT/'packages/campaign/chapter06_npcs/huang.model.json').read_bytes());uid=p['entities'][0]['id']
 dealer={'id':'unit/peer/dealer','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':10000}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'abilities':['ability/peer/hit'],'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(dealer)
 p['abilities'].append({'id':'ability/peer/hit','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'damage','target':2,'damage_type':'true','scale':1}]},'timeline':[]})
 item={'definition':uid,'instanceAlias':'native_npc','position':{'row':0,'col':0}}
 if buff:
  p['buffs'].append(buff);item['components']={'buffs':{'initial':p['entities'][0]['components']['buffs']['initial']+[buff['id']]}}
 p['scenarioDraft']={'id':'scene/peer/huang','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':5},'objectives':{},'resources':{},'initialEntities':[item,{'definition':dealer['id'],'instanceAlias':'dealer','position':{'row':1,'col':4}}]}
 return p
def make(p):INPUTS.append(deepcopy(p));reg=providers();return Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=6471)
def hit(s,t):s.submit({'action':'skill','source':'dealer','ability':'ability/peer/hit'},at=t)
def capture(s,k):CAPTURES.append({'case':k,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
def test_base_once_recover_and_real_six_second_floor_then_true_death():
 s=make(fixture());hit(s,10);hit(s,20);hit(s,191);s.advance(11);assert s.ctx.resources.current('native_npc','hp')==1153.5;s.advance(10);assert s.ctx.resources.current('native_npc','hp')==1152.5;s.advance(171);capture(s,'once_base')
 assert not s.ctx.active('native_npc') and len([e for e in s.session.events if e['type']=='resource.changed' and e['payload']['target']==2 and e['payload']['resource']=='hp' and e['payload']['delta']>0])==1
def test_dynamic_effective_max_hp_changes_quarter_trigger_threshold():
 p=fixture({'id':'buff/peer/maxhp','kind':'buff','modifiers':[{'attribute':'max_hp','layer':'flat','value':1000}]});p['entities'][-1]['components']['attributes']['base']['atk']=1605
 s=make(p);hit(s,10);s.advance(12);capture(s,'dynamic_quarter_threshold')
 assert s.ctx.resources.capacity('native_npc','hp')==3305 and s.ctx.resources.current('native_npc','hp')==2352.5
def test_buff_derived_heal_free_blocks_native_recovery_but_consumes_once():
 s=make(fixture({'id':'buff/peer/heal_free','kind':'buff','selection_flags':{'heal_free':True}}));hit(s,10);s.advance(12);capture(s,'buff_heal_free')
 assert s.ctx.resources.current('native_npc','hp')==1 and not [e for e in s.session.events if e['type']=='heal.accepted']
 assert not [b for b in s.ctx.get('native_npc',('buffs','instances'),[]) if b['definition']=='buff/ch6/npc/huang_once']
