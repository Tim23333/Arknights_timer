from copy import deepcopy
from pathlib import Path
import json
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.buff_application import pure_attributes
from tools.chapter08_bsnake.screen_policy_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim.tools.replay import replay
ROOT=Path(__file__).resolve().parents[2];MODULE=ROOT/'packages/campaign/chapter08_consumers/bsnake/first_screen.module.v2.json';INPUTS=[];CAPTURES=[]
SCREEN='buff/ch8/source/bsnake_s[screen_attack]';INV='buff/ch8/source/reborn_up[invincible]'
def package(witness=False):
 p=json.loads(MODULE.read_bytes());boss=p['entities'][0]['id'];p['entities'].append({'id':'unit/peer/director','kind':'entity','components':{'attributes':{'base':{'atk':1000}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'abilities':['ability/peer/kill','ability/peer/strike']}})
 p['abilities'] += [{'id':'ability/peer/kill','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'instant_kill','target':2,'parameters':{'cause':'peer_first_screen','skip_rebirth':False}}]},'timeline':[]},{'id':'ability/peer/strike','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'damage','target':2,'damage_type':'true','scale':1}]},'timeline':[]}]
 initial=[{'definition':boss,'instanceAlias':'boss','position':{'row':2,'col':6}},{'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':0}}]
 for row,res,motion,free in [(1,17,1,False),(2,37,2,False),(3,53,1,True)]:
  eid='unit/peer/recipient'+str(row);p['entities'].append({'id':eid,'kind':'entity','tags':['recipient'],'components':{'attributes':{'base':{'max_hp':100000,'atk':0,'def':233,'mres':res}},'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},'selection_state':{'side':0,'motion':motion,'category':1,'unit_type':1,'target_free':free},'spatial':{'motion_mode':1 if motion==2 else 0},'lifecycle':{'policy':'policy/ark_lifecycle'}}});initial.append({'definition':eid,'instanceAlias':'recipient'+str(row),'position':{'row':row,'col':3}})
 eligibility=deepcopy(p['projectiles'][0]['collision']['parameters']['eligibility'])
 for ignore in (0,1):
  spec=deepcopy(eligibility['parameters']);spec['source_configuration']['_ignoreTargetFree']=ignore;p['selectors'].append({'id':'selector/peer/ignore'+str(ignore),'kind':'selector','region':{'type':'all'},'filters':[],'limit':None,'eligibility':{'rule':eligibility['rule'],'parameters':spec}})
 p['manifest']['requires']+=['selector/peer/ignore0','selector/peer/ignore1']
 if witness:
  p['entities'][0]['components']['abilities'].append('ability/peer/ordinary');p['selectors'].append({'id':'selector/peer/ordinary','kind':'selector','region':{'type':'all'},'filters':[{'tag':'recipient'}],'limit':1});p['abilities'].append({'id':'ability/peer/ordinary','kind':'ability','activation':{'mode':'automatic_attack'},'selector':'selector/peer/ordinary','timeline':[{'at':0,'effect':{'op':'emit','event':'peer.ordinary.witness'}}]})
 p['scenarioDraft']={'id':'scene/peer/first_screen','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':8},'initialEntities':initial};return p
def make(witness=False):p=package(witness);INPUTS.append(deepcopy(p));reg=providers();return Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=88817)
def capture(s,name):CAPTURES.append({'case':name,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
def test_real_source28s10volleys_with_flying_and_targetfree_different_RES_damage_and_invulnerability_gates(tmp_path):
 s=make();s.submit({'action':'skill','source':'director','ability':'ability/peer/kill'},at=1)
 for t in (900,1100,1441):s.submit({'action':'skill','source':'director','ability':'ability/peer/strike'},at=t)
 s.advance(500);screen=next(b for b in s.ctx.get('boss',('buffs','instances')) if b['definition']==SCREEN);assert screen['expires_at']==991 and 22 in s.ctx.spatial.selection_state('boss')['abnormal_flags']
 pin=write_ordered(tmp_path/'firstscreen500.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'firstscreen500.json',pin),providers=providers());s.advance(600);r.advance(600)
 assert s.ctx.resources.current('boss','mode')==1 and s.ctx.resources.current('boss','hp')==37500
 before=s.checkpoint();assert not s.ctx.spatial.qualifies('director',2,'selector/peer/ignore0') and s.ctx.spatial.qualifies('director',2,'selector/peer/ignore1') and s.checkpoint()==before
 s.advance(350);r.advance(350);h=replay(s.program,s.export_replay(),providers=providers());capture(s,'source_numbers');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==2];assert len(hits)==20
 for ref,res in [(4,17),(5,37)]:
  actual=[e['payload']['amount'] for e in hits if e['payload']['target']==ref];assert len(actual)==10 and all(abs(x-1155*(1-res/100))<1e-9 for x in actual)
 assert s.ctx.resources.current('recipient3','hp')==100000 and s.ctx.resources.current('boss','hp')==36500 and pure_attributes(s.ctx,2)['max_hp']==75000
 assert [e['time'] for e in s.session.events if e['type']=='source.bsnake.screen.volley']==list(range(211,812,60))
 assert len([e for e in s.session.events if e['type']=='projectile.launched'])==30 and len([e for e in s.session.events if e['type']=='source.bsnake.hint.requested'])==1
def test_controlled_ordinary_bound_selector_witness_suppressed_through_screen_then_resumes(tmp_path):
 s=make(True);s.submit({'action':'skill','source':'director','ability':'ability/peer/kill'},at=1);s.advance(500);pin=write_ordered(tmp_path/'witness500.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'witness500.json',pin),providers=providers());s.advance(520);r.advance(520);h=replay(s.program,s.export_replay(),providers=providers());capture(s,'controlled_witness');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 times=[e['time'] for e in s.session.events if e['type']=='peer.ordinary.witness'];assert times and not any(151<=t<991 for t in times) and any(t>=991 for t in times)
