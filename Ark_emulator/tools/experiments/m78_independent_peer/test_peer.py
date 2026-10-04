import json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m78_owned_attachment_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
SRC=json.loads((ROOT/'packages/campaign/chapter04_dmage/source.reference.json').read_bytes())
def make(normal=False,high=False):
 p=json.loads((ROOT/'packages/campaign/chapter04_dmage/module.reference.json').read_bytes());uid=p['entities'][0]['id']
 target={'id':'unit/peer','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':9000,'def':17,'mres':20,'block_count':1,'taunt_level':0}},'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'abilities':['ability/peer/withdraw','ability/peer/silence','ability/peer/move','ability/peer/atk'],'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground','parameters':{'max_instances':3}},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(target)
 p['selectors'].append({'id':'selector/peer/source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
 p['buffs'].append({'id':'buff/peer/silence','kind':'buff','selection_flags':{'abnormal_flags':[12]}})
 p['abilities'].extend([{'id':'ability/peer/withdraw','kind':'ability','selector':'selector/peer/source','activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdrawn'}}]},'timeline':[]},{'id':'ability/peer/silence','kind':'ability','selector':'selector/peer/source','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/peer/silence'}]},'timeline':[]},{'id':'ability/peer/move','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':1,'col':7}}]},'timeline':[]},{'id':'ability/peer/atk','kind':'ability','selector':'selector/peer/source','activation':{'mode':'manual','on_start':[{'op':'modify_attribute','attribute':'atk','value':1000}]},'timeline':[]}])
 initial=[{'definition':uid,'instanceAlias':'caster','position':{'row':1,'col':1}},{'definition':'unit/peer','instanceAlias':'victim','position':{'row':1,'col':2}}]
 if normal:
  p['entities'][0]['components']['resources']['lasso_uses']['initial']=0
  p['buffs'].append({'id':'buff/peer/hold','kind':'buff','duration_seconds':1/30,'control':{'attack':False}})
  initial[0]['components']={'buffs':{'initial':['buff/peer/hold']}}
  initial[0]['route']={'motionMode':0,'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':6},'checkpoints':[]}
  initial[1]['position']={'row':1,'col':1}
 if high:initial.append({'definition':'unit/peer','instanceAlias':'other','position':{'row':2,'col':1},'components':{'attributes':{'base':{'taunt_level':20}}}})
 p['scenarioDraft']={'id':'scene/peer','ruleset':'ruleset/ark_standard','roster':['unit/peer'],'map':{'rows':4,'cols':9},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':initial}
 INPUTS.append(p);return Engine.create(Compiler().compile(p),seed=780403)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def link(s):return next(iter(s.ctx.attachments.state()['instances'].values()))
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def test_normal_source2_actual_blocker_hard_eligibility():
 assert SRC['source_graph']['normal_attack']['raw']['_selectTargetSource']==2
 s=make(True,True);s.advance(2);assert s.ctx.spatial.blocked_by('caster')==s.session.world.resolve('victim')
 s.advance(36);capture(s,'normal_source2_blocker');assert ev(s,'damage.accepted')[0]['payload']['target']==s.session.world.resolve('victim')
@pytest.mark.parametrize('at',[28,40])
@pytest.mark.parametrize('ability',['withdraw','silence'])
def test_public_flight_and_held_cancellation(at,ability,tmp_path):
 s=make();s.submit({'action':'skill','source':'other','ability':'ability/peer/'+ability},at=at) if False else None
 # A separate free actor issues public commands while victim is controlled.
 p=INPUTS.pop();p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer','instanceAlias':'other','position':{'row':3,'col':8}});INPUTS.append(p);s=Engine.create(Compiler().compile(p),seed=780403)
 s.submit({'action':'skill','source':'other','ability':'ability/peer/'+ability},at=at)
 s.advance(27);pin=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',pin));s.advance(40);r.advance(40)
 capture(s,f'{at}_{ability}');assert s.checkpoint()==r.checkpoint();assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
 assert not link(s)['active'];assert not s.ctx.get('victim',('buffs','instances'));assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.attachment.step']
def test_raw_range_is_acquisition_only_and_600_live_packets():
 s=make();s.advance(36);s.ctx.set('victim',('spatial','position'),{'row':1,'col':7});old=s.ctx.resources.current('victim','hp');s.advance(2);assert link(s)['active'];assert old-s.ctx.resources.current('victim','hp')==pytest.approx(2*500*.35/30*.8)
 capture(s,'range_capture_policy');assert all(e['payload']['damage_flags']=={'source_attack_type':'BUFF','ignore_for_sp':False} for e in ev(s,'damage.accepted'));assert not ev(s,'attack.accepted')
def test_target_death_breaks_immediately_and_external_distinct_buff_survives():
 s=make();s.advance(36);s.ctx.buffs.apply('victim','victim','buff/peer/silence');s.ctx.lifecycle.retire('caster','withdrawn');capture(s,'external_distinct_buff')
 rows=s.ctx.get('victim',('buffs','instances'));assert len(rows)==1 and rows[0]['definition']=='buff/peer/silence';assert not link(s)['active']
