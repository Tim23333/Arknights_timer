"""Both exact Boss consumers: existing class exclusion and real late kill."""
from pathlib import Path
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.chapter06_boss.shield_filters.build_modules import ROOT
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
COLD=ROOT/'packages/campaign/chapter06_cold/model.json'
DIRS={'ordinary':'frstar2_v3','story':'frstar2_s_v2'}
def package(which,*,side=0,unit_type=1,dormant=False):
 p=json.loads((ROOT/'packages/campaign/chapter06_boss'/DIRS[which]/'model.json').read_bytes());boss=p['entities'][0];shield=next(a['id'] for a in p['definitions'] if a['kind']=='ability' and 'tile_selector' in a);start=1050 if which=='ordinary' else 690
 # Pure controlled isolation: native Shield initial cooldown/frame/count remain.
 # Other source abilities disabled only in this probe to expose exact capture.
 for e in boss['components']['ability_arbitration']['entries']:
  if e['ability']!=shield:e['condition']='False'
 p['manifest']['metadata']['probe_policy']='Only unrelatedarbitration conditions disabled for capture qualification; not whole/native Bossnoattack claim'
 npc={'id':'unit/test/shield/victim','kind':'entity','tags':['player','classification_probe'],'components':{'attributes':{'base':{'max_hp':1000000,'atk':0,'def':300,'mres':50}},'resources':{'hp':{'role':'health','initial':1000000,'capacity':1000000}},'selection_state':{'side':side,'motion':1,'category':1,'unit_type':unit_type},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 if side!=0:npc['tags'].remove('player')
 p['entities'].append(npc);aid='ability/test/shield/activate'
 p['entities'].append({'id':'unit/test/shield/controller','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':0}},'resources':{'hp':{'role':'health','initial':100,'capacity':100}},'spatial':{},'abilities':[aid]}})
 p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'timeline':([{'at':0,'effect':{'op':'activate_predefined','target':'battle','parameters':{'key':'victim'}}}] if dormant else [])})
 victim={'definition':npc['id'],'instanceAlias':'victim','position':{'row':2,'col':3}}
 if dormant:victim.update({'active':False,'registration_key':'victim'})
 p['scenarioDraft']={'id':'scene/shield/'+which,'ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':5,'default_tile':{'buildableType':0,'passableMask':1},'tiles':[{'buildableType':1 if (r,c)==(2,3) else 0,'passableMask':1} for r in range(5) for c in range(5)]},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':boss['id'],'instanceAlias':'boss','position':{'row':2,'col':2}},victim,{'definition':'unit/test/shield/controller','instanceAlias':'controller','position':{'row':4,'col':4}}]}
 if which=='ordinary':p['scenarioDraft']['branches']={'frstar_frosts':{'loop':False,'phases':[{'pre_delay_seconds':0,'actions':[]}]}}
 return p,shield,start,aid
def make(which,**kw):
 p,a,t,c=package(which,**kw);reg=providers();return Engine.create(Compiler(providers=reg).compile(p,packages=[COLD]),providers=reg,seed=6217),a,t,c
def events(s,name):return [e for e in s.session.events if e['type']==name]
@pytest.mark.parametrize('which',DIRS)
@pytest.mark.parametrize('mask',[1,5])
def test_actual_existing_friendly_char_without_deployable_excluded(which,mask):
 s,a,t,_=make(which,unit_type=mask);s.session.advance(t+57)
 assert not events(s,'tile.selection') and not [e for e in events(s,'ability.started') if e['payload']['ability']==a]
 assert s.ctx.alive('victim') and s.ctx.resources.current('victim','hp')==1000000
@pytest.mark.parametrize('which',DIRS)
@pytest.mark.parametrize('side,mask',[(1,1),(0,4)])
def test_actual_other_side_char_or_friendly_token_not_overexcluded(which,side,mask):
 s,a,t,_=make(which,side=side,unit_type=mask);s.session.advance(t+56)
 selected=events(s,'tile.selection');assert len(selected)==1 and selected[0]['time']==t
 assert len([e for e in s.session.world.entities() if 'sealed_floor' in e.get('tags',[])])==1
 if side==1:assert s.ctx.alive('victim')
@pytest.mark.parametrize('which',DIRS)
def test_actual_dormant_excluded_from_projection_then_publiclate_activation_killed55(which):
 s,a,t,c=make(which,dormant=True);s.submit({'action':'skill','source':'controller','ability':c},at=t+1);s.session.advance(t+56)
 assert len(events(s,'tile.selection'))==1 and events(s,'tile.selection')[0]['time']==t
 died=[e for e in events(s,'entity.died') if e['payload'].get('target')==s.session.world.resolve('victim')];assert len(died)==1 and died[0]['time']==t+55
 assert s.ctx.resources.current('victim','hp')==0 and not s.ctx.alive('victim')
@pytest.mark.parametrize('which',DIRS)
@pytest.mark.parametrize('relative',[-1,1])
def test_actual_new_filter_before_capture_or_lateactivation_diskcp_head(which,relative,tmp_path):
 s,a,t,c=make(which,dormant=True);s.submit({'action':'skill','source':'controller','ability':c},at=t+1);tick=t+relative;s.session.advance(tick);p=tmp_path/'shield.json';h=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,h),providers=providers());s.session.advance(t+70-tick);r.session.advance(t+70-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
