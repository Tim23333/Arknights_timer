import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
FROST=ROOT/'packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json';DMAGE=ROOT/'packages/campaign/chapter04_dmage/module.immunity_guard.reference.json'
assert hashlib.sha256(FROST.read_bytes()).hexdigest()=='41bfb7ff3e7dc2cf9efadcdcf2007c7e70cdcb311b5a9712eda8232eca64c5d0'
assert hashlib.sha256(DMAGE.read_bytes()).hexdigest()=='2b3804fcd456e456b137b8145afe655d031db4dbf331a6115af3fded168f51e6'
def ev(s,kind):return [thaw(e) for e in s.session.events if e['type']==kind]
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay()})
def create(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=940493)
def exact(s,tmp,n=8):
 pin=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',pin));s.advance(n);r.advance(n)
 assert s.checkpoint()==r.checkpoint();assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
 return pin
def hero():return {'id':'unit/peer/hero','kind':'entity','tags':['player','ground'],'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'attributes':{'base':{'max_hp':15000,'atk':1,'def':0,'mres':20,'block_count':0}},'resources':{'hp':{'initial':15000,'capacity':15000,'role':'health'}},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
def environment(amount,target=2):return {'op':'no_source_damage','target':target,'fixed_amount':amount,'damage_type':'true','attack_type':'NONE','origin':{'kind':'independent_environment_probe','cell':{'row':1,'col':1}},'ignore_for_sp':False,'damage_without_modify':False,'node_is_env_damage':False,'env_blackboard_injected':True,'environmental':True,'rules':{'damage.pipeline':'rule/peer/environment'}}
def environment_rule():return {'id':'rule/peer/environment','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}],'output':'nodes.result'}}
def frost_fixture():
 p=json.loads(FROST.read_bytes());p['entities'][0]['dependencies']=['buff/m70/sleep','buff/m86/chen_source_stun'];director=hero();director['id']='unit/peer/director';director['components']['abilities']=['ability/peer/sleep','ability/peer/stun'];p['entities'].append(director)
 p['selectors'].append({'id':'selector/peer/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}],'limit':1})
 for name,buff in [('sleep','buff/m70/sleep'),('stun','buff/m86/chen_source_stun')]:p['abilities'].append({'id':'ability/peer/'+name,'kind':'ability','selector':'selector/peer/boss','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':buff}]},'timeline':[]})
 p['rules'].append(environment_rule());p['scenarioDraft']={'id':'scene/peer/frost','ruleset':'ruleset/ark_standard','map':{'rows':4,'cols':9},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':1,'col':1}},{'definition':director['id'],'instanceAlias':'director','position':{'row':3,'col':8}}],'scheduledEffects':[{'at':2,'effect':environment(25000)},{'at':160,'effect':environment(25000)}]}
 return p
def test_true_frost_native_immunity_sleep_rebirth_and_no_source_final_claim(tmp_path):
 p=frost_fixture();s=create(p);s.submit({'action':'skill','source':'director','ability':'ability/peer/sleep'},at=0);s.submit({'action':'skill','source':'director','ability':'ability/peer/stun'},at=1);s.submit({'action':'skill','source':'director','ability':'ability/peer/sleep'},at=154)
 s.advance(2);state=s.ctx.spatial.selection_state('boss',DEFAULT_STATE);assert state['abnormal_immunes']==[0,12,16,25] and state['abnormal_combo_immunes']==[0]
 assert s.ctx.buffs.controls('boss')=={'move':True,'attack':True,'abilities':True,'block':True}
 s.advance(1);assert s.ctx.resources.current('boss','hp')==0 and s.ctx.alive('boss') and not s.ctx.active('boss') and s.ctx.state()['kills']==0;assert not ev(s,'combat.kill')
 assert not any(b['definition']=='buff/ch4/frstar/initial_sleep_immune' for b in s.ctx.get('boss',('buffs','instances')))
 exact(s,tmp_path,150);assert s.session.time==153 and s.ctx.resources.current('boss','hp')==25000
 s.advance(2);assert s.ctx.buffs.controls('boss')['attack'] is False;assert s.ctx.spatial.selection_state('boss',DEFAULT_STATE)['abnormal_combos']==[0]
 s.advance(6);capture(s,'frost_none_final');assert not s.ctx.alive('boss') and s.ctx.state()['kills']==1
 kills=ev(s,'combat.kill');assert len(kills)==1 and kills[0]['payload']['source'] is None and kills[0]['payload']['origin']==environment(25000)['origin']
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def lasso_fixture(immune_target=False,immune_source=False):
 p=json.loads(DMAGE.read_bytes());f=json.loads(FROST.read_bytes())
 for key in ['rules','buffs','abilities','selectors']:p[key].extend(f[key])
 target=hero();target['dependencies']=['buff/m70/sleep'];p['entities'].append(target)
 if immune_target:target['components']['selection_state']['abnormal_immunes']=deepcopy(f['entities'][0]['components']['selection_state']['abnormal_immunes'])
 if immune_source:p['entities'][0]['components']['selection_state']['abnormal_immunes']=[12]
 director=hero();director['id']='unit/peer/director';director['components']['abilities']=['ability/peer/silence','ability/peer/withdraw','ability/peer/external'];p['entities'].append(director)
 p['buffs'].append({'id':'buff/peer/silence','kind':'buff','selection_flags':{'abnormal_flags':[12]}})
 targetbuff=p['definitions'][0]['target_buff'];p['abilities'].extend([{'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]} for name,effect in [('silence',{'op':'apply_buff','target':2,'buff':'buff/peer/silence'}),('withdraw',{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}),('external',{'op':'apply_buff','target':3,'buff':targetbuff})]])
 p['scenarioDraft']={'id':'scene/peer/owned_immunity','ruleset':'ruleset/ark_standard','map':{'rows':4,'cols':9},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'caster','position':{'row':1,'col':1}},{'definition':target['id'],'instanceAlias':'victim','position':{'row':1,'col':2}},{'definition':director['id'],'instanceAlias':'director','position':{'row':3,'col':8}}]}
 return p
def link(s):return next(iter(s.ctx.attachments.state()['instances'].values()))
def test_source_owned_target_stun_native_immunity_must_not_disable_control_but_buff_damage_survives():
 s=create(lasso_fixture(True));s.advance(33);capture(s,'owned_stun_vs_native_immunity')
 assert s.ctx.spatial.selection_state('victim',DEFAULT_STATE)['abnormal_flags']==[]
 assert s.ctx.resources.current('victim','hp')==pytest.approx(15000-4*500*.35/30*.8)
 assert all(e['payload']['damage_flags']['source_attack_type']=='BUFF' for e in ev(s,'damage.accepted'))
 assert s.ctx.buffs.controls('victim')=={'move':True,'attack':True,'abilities':True,'block':True}
@pytest.mark.parametrize('immune',[False,True])
def test_source_silence_immunity_and_cleanup_preserve_external_same_definition(immune,tmp_path):
 s=create(lasso_fixture(False,immune));s.submit({'action':'skill','source':'director','ability':'ability/peer/external'},at=28);s.submit({'action':'skill','source':'director','ability':'ability/peer/silence'},at=40);s.submit({'action':'skill','source':'director','ability':'ability/peer/withdraw'},at=50)
 s.advance(42);assert link(s)['active'] is immune;assert all(e['time']<40 for e in ev(s,'damage.accepted')) if not immune else any(e['time']==41 for e in ev(s,'damage.accepted'))
 exact(s,tmp_path,10);capture(s,'source_silence_'+str(immune));assert not link(s)['active']
 targetbuff=s.program.definitions[link(s)['definition']]['target_buff'];rows=[b for b in s.ctx.get('victim',('buffs','instances')) if b['definition']==targetbuff]
 assert len(rows)==1 and rows[0]['source']==s.session.world.resolve('director')
 assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.attachment.step']
