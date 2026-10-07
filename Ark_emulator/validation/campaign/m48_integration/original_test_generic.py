import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]
def fixture():
 effect={'op':'area','center':'target','membership_rule':'rule/cells','parameters':{'offsets':[[r,c] for r in (-1,0,1) for c in (-1,0,1)]},'filters':[{'tag':'victim'}],'effects':[{'op':'damage','damage_type':'true','amount':10}]}
 unit=lambda name,tags,hp:{'id':'unit/'+name,'kind':'entity','tags':tags,'components':{'attributes':{'base':{'max_hp':hp,'atk':10,'def':0,'mres':0}},'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 source=unit('caster',['caster'],100);source['components']['abilities']=['ability/packet']
 return {'manifest':{'requires':['preset/ark_standard']},'entities':[source,unit('victim',['victim'],100)],'rules':[{'id':'rule/cells','kind':'rule','contract':'area.members','implementation':{'type':'provider','provider':'ark.area.cell_offsets'}}],'selectors':[{'id':'selector/main','kind':'selector','region':{'type':'all'},'filters':[{'tag':'victim'}],'limit':1}], 'abilities':[{'id':'ability/packet','kind':'ability','selector':'selector/main','activation':{'mode':'manual'},'timeline':[{'at_seconds':0,'effect':effect}]}], 'scenarioDraft':{'id':'scene/area','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':8,'cols':8},'initialEntities':[{'definition':'unit/caster','instanceAlias':'src','position':{'row':0,'col':0}},*[{'definition':'unit/victim','instanceAlias':name,'position':{'row':r,'col':c}} for name,r,c in [('main',3,3),('inside',4.49,4.49),('outside',4.5,4.5),('edge',2.5,2.5)]]]}}
def make(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':4601,'fixture':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=4601)
def test_grid_cells_corner_projection_and_disk_command_replay(tmp_path):
 s=make(fixture());s.submit({'action':'skill','source':'src','ability':'ability/packet'},at=1);s.advance(1);pin=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',pin));s.advance(3);r.advance(3)
 assert [s.ctx.resources.current(x,'hp') for x in ['main','inside','outside','edge']]==[90,90,100,90]
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
 assert len([e for e in s.session.events if e['type']=='damage.accepted'])==3
@pytest.mark.parametrize('expr',['[inputs.candidates[0].id, inputs.candidates[0].id]','[9999]','[True]','None'])
def test_invalid_membership_full_atomic_rollback(expr):
 p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':expr};s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.effects.execute('src',['main'],p['abilities'][0]['timeline'][0]['effect'])
 assert s.checkpoint()==before
@pytest.mark.parametrize('change',[lambda e:e.update(membership_rule='selector/main'),lambda e:e.update(membership_rule=''),lambda e:e.update(membership_rule=None),lambda e:e.update(op='damage'),lambda e:e.update(op='emit',event='peer.invalid'),lambda e:e.update(radius=1),lambda e:e['parameters'].update(offsets=[[True,0]]),lambda e:e['parameters'].update(offsets=[[0,.5]])])
def test_bad_profiles_compile_rejected(change):
 p=fixture();change(p['abilities'][0]['timeline'][0]['effect'])
 with pytest.raises(ValueError):Compiler().compile(p)
def test_retired_center_explicit_position_area_still_settles():
 s=make(fixture());s.ctx.lifecycle.retire('main','withdrawn');e=deepcopy(fixture()['abilities'][0]['timeline'][0]['effect']);e['center_position']={'row':3,'col':3};s.ctx.effects.execute('src',['main'],e)
 assert s.ctx.resources.current('inside','hp')==90 and s.ctx.resources.current('main','hp')==100

def test_partial_damage_rng_failure_rolls_back_whole_area():
 p=fixture();p['rules'].append({'id':'rule/fail','kind':'rule','contract':'buff.duration','implementation':{'type':'expression','expression':'1 / 0'}})
 p['buffs']=[{'id':'buff/fail','kind':'buff','duration_seconds':1,'duration_rule':'rule/fail'}]
 effect=p['abilities'][0]['timeline'][0]['effect'];effect['effects'].insert(0,{'op':'random','stream':'imp','probability':1,'on_success':[{'op':'emit','event':'peer.random_pre_damage'}]});effect['effects'].append({'op':'apply_buff','buff':'buff/fail'})
 s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.effects.execute('src',['main'],effect)
 assert s.checkpoint()==before

def test_custom_context_scope_and_calc_operands_observable_public_replay(tmp_path):
 p=fixture();p['rules'][0]['implementation']={'type':'expression','expression':"[inputs.candidates[0].id] if ctx.source.id != ctx.target.id and ctx.ability.id == 'ability/packet' and ctx.effect.op == 'area' and ctx.rule_scope.ability['area.members'] == 'rule/cells' else []"}
 p['abilities'][0]['rules']={'area.members':'rule/cells'}
 s=make(p);s.submit({'action':'skill','source':'src','ability':'ability/packet'},at=1);s.advance(3)
 calc=[e for e in s.session.events if e['type']=='calculation' and e['payload'].get('calculation_id')=='area.members']
 assert len(calc)==1
 payload=calc[0]['payload'];assert payload['trace']['inputs']['center_position']=={'row':2.5,'col':2.5} and len(payload['trace']['inputs']['candidates'])==4
 assert list(payload['value'])==[s.session.world.resolve('main')]
 assert s.ctx.resources.current('main','hp')==90 and s.ctx.resources.current('inside','hp')==100
 pin=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',pin));s.advance(1);r.advance(1);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
