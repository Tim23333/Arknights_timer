import sys,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m61_rebirth_candidate'));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def fixture():
 p=json.loads((ROOT/'packages/campaign/chapter04_boss/m61/rebirth.reference_model.json').read_bytes());p['entities'].append({'id':'unit/director','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'atk':25000,'max_hp':10000,'def':0,'mres':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/knockdown']}});p['selectors']=[{'id':'selector/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}],'limit':1},{'id':'selector/director','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}],'limit':1}];p['abilities']=[{'id':'ability/knockdown','kind':'ability','selector':'selector/boss','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'true'}]},'timeline':[]},{'id':'ability/synthetic_phase_probe','kind':'ability','selector':'selector/director','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'true'}]},'timeline':[],'metadata':{'synthetic_test_only':'ATK effective packet inspection, not native FrostNova ordinary attack'}}];p['entities'][0]['components']['abilities']=['ability/synthetic_phase_probe']
 p['scenarioDraft']={'id':'scene/source/frstar/rebirth','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':5},'initialEntities':[{'definition':'unit/ch4/frstar/level0','instanceAlias':'boss','position':{'row':1,'col':1}},{'definition':'unit/director','instanceAlias':'director','position':{'row':2,'col':4}}]};return p
def test_exact_25000_first0_wait150ticks_restore25000_and_atk630_then_second_real_death(tmp_path):
 p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=6110);ref=s.session.world.resolve('boss');s.submit({'action':'skill','source':'boss','ability':'ability/synthetic_phase_probe'},at=1);s.submit({'action':'skill','source':'boss','ability':'ability/synthetic_phase_probe'},at=152);s.submit({'action':'skill','source':'director','ability':'ability/knockdown'},at=2);s.submit({'action':'skill','source':'director','ability':'ability/knockdown'},at=153);s.advance(3)
 assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.state()['kills']==0
 path=tmp_path/'frost.ordered.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(149);r.advance(149);assert s.ctx.resources.current('boss','hp')==0 and s.ctx.alive('boss')
 s.advance(1);r.advance(1);assert s.ctx.resources.current('boss','hp')==25000 and s.session.world.resolve('boss')==ref
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==ref]==[(1,420),(152,630)]
 s.advance(2);r.advance(2);assert not s.ctx.alive('boss') and s.ctx.state()['kills']==1 and len([e for e in s.session.events if e['type']=='combat.kill'])==1
 assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
def test_raw_half_and_reference_full_are_distinct_and_no_numeric_bool_immunity_fake():
 p=fixture();meta=p['entities'][0]['metadata'];assert meta['raw_hp_recharge_ratio']==.5 and meta['declared_restore_ratio']==1 and meta['native_variant_id']=='enemy_1505_frstar@0/9d1e3d01ef79ae3e'
 assert not any('immune' in k for k in p['entities'][0]['components']['attributes']['base'])
 assert any('M70' in x for x in p['manifest']['metadata']['model_gaps'])
def test_configured_half_profile_is_replaceable_but_not_the_selected_reference_profile():
 p=fixture();p['entities'][0]['components']['rebirth']['restore_ratio']=.5;s=Engine.create(Compiler().compile(p),seed=6111);s.submit({'action':'skill','source':'director','ability':'ability/knockdown'},at=0);s.advance(151)
 assert s.ctx.resources.current('boss','hp')==12500 and s.ctx.attributes.value('boss','atk')==630
