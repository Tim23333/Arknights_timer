import json,hashlib
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest
INPUTS=[]
def fixture(second=False,remote=False):
 actor=lambda ident,tags:{'id':'unit/'+ident,'kind':'entity','tags':tags,'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'atk':100,'def':10}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 root=actor('root',['emitter']);root['components']['buffs']={'initial':['buff/root']}
 a=actor('a',['member']);a['components']['abilities']=['ability/leave'];b=actor('b',['member','victim'])
 p={'manifest':{'requires':['preset/ark_standard']},'entities':[root,a,b],'buffs':[{'id':'buff/root','kind':'buff','aura':{'selector':'selector/members','buff':'buff/child'}},{'id':'buff/child','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':5}],'on_remove':[{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}]}],'selectors':[{'id':'selector/members','kind':'selector','region':{'type':'circle','radius':2},'filters':[{'tag':'member'},{'state':'alive'}]},{'id':'selector/b','kind':'selector','region':{'type':'all'},'filters':[{'tag':'victim'}],'limit':1}], 'abilities':[{'id':'ability/leave','kind':'ability','selector':'selector/b','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':6}},{'op':'damage','damage_type':'physical'}]},'timeline':[]}], 'scenarioDraft':{'id':'scene/peer45','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':8},'initialEntities':[{'definition':'unit/root','instanceAlias':'root','position':{'row':0,'col':3}},{'definition':'unit/a','instanceAlias':'a','position':{'row':0,'col':4}},{'definition':'unit/b','instanceAlias':'b','position':{'row':0,'col':2}}]}}
 if second:
  extra=actor('extra',['emitter']);extra['components']['buffs']={'initial':['buff/extra']};p['entities'].append(extra);p['buffs'] += [{'id':'buff/extra','kind':'buff','aura':{'selector':'selector/members','buff':'buff/extra_child'}},{'id':'buff/extra_child','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':7}]}];p['scenarioDraft']['initialEntities'].append({'definition':'unit/extra','instanceAlias':'extra','position':{'row':0,'col':1}})
 if remote:
  root['components'].pop('buffs');remote_unit=actor('remote',['remote']);remote_unit['components']['abilities']=['ability/setup'];p['entities'].append(remote_unit);p['selectors'].append({'id':'selector/root','kind':'selector','region':{'type':'all'},'filters':[{'tag':'emitter'}],'limit':1});p['abilities'].append({'id':'ability/setup','kind':'ability','selector':'selector/root','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/root'}]},'timeline':[]});p['scenarioDraft']['initialEntities'].append({'definition':'unit/remote','instanceAlias':'remote','position':{'row':2,'col':7}})
 return p
def make(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':45091,'fixture':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=45091)
@pytest.mark.parametrize('second,expected_hp',[(False,10),(True,17)])
def test_samecast_source_retire_and_other_source_survives_disk_replay(second,expected_hp,tmp_path):
 s=make(fixture(second));s.submit({'action':'skill','source':'a','ability':'ability/leave'},at=2);s.advance(1);pin=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',pin));s.advance(3);r.advance(3)
 assert not s.ctx.alive('root') and s.ctx.resources.current('b','hp')==expected_hp
 if second:assert s.ctx.alive('extra') and [x['definition'] for x in s.ctx.get('b',('buffs','instances'))]==['buff/extra_child']
 else:assert s.ctx.get('b',('buffs','instances'))==[]
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_remote_actual_source_retired_center_alive_samecast():
 s=make(fixture(remote=True));s.submit({'action':'skill','source':'remote','ability':'ability/setup'},at=0);s.submit({'action':'skill','source':'a','ability':'ability/leave'},at=2);s.advance(4)
 assert s.ctx.alive('root') and not s.ctx.alive('remote') and s.ctx.resources.current('b','hp')==10
 assert s.ctx.get('b',('buffs','instances'))==[] and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_failure_after_real_retire_and_rng_restores_guard_and_valid_retry():
 s=make(fixture());before=s.checkpoint();old=s.ctx.lifecycle.retire
 def fail(ref,reason):
  old(ref,reason);s.session.random.sample('imp');s.session.schedule('domain.entity.expire',{'target':ref},90);raise RuntimeError('peer after actual retire')
 s.ctx.lifecycle.retire=fail
 with pytest.raises(RuntimeError):s.ctx.movement.displace('a','a',{'position':{'row':0,'col':6}},None)
 assert s.checkpoint()==before and not s.ctx.buffs._reconciling and s.ctx.buffs._removal_depth==0
 s.ctx.lifecycle.retire=old;s.ctx.movement.displace('a','a',{'position':{'row':0,'col':6}},None)
 assert not s.ctx.alive('root') and s.ctx.get('b',('buffs','instances'))==[]
def test_random_membership_single_draw_per_explicit_reconcile_no_child_repeat():
 p=fixture();p['buffs'][1].pop('on_remove');p['selectors'][0].update(limit=1,ordering='random',parameters={'random_stream':'imp'})
 s=make(p);before=s.session.random.snapshot()['samples'];s.ctx.buffs.reconcile();after=s.session.random.snapshot()['samples']
 assert len(after)-len(before)==1
 assert sum(len(s.ctx.get(x,('buffs','instances'))) for x in ['a','b'])==1
