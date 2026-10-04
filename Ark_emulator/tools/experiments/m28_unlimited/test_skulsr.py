"""Unresolved threshold policies remain two explicit, different model inputs."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m28_unlimited_projectile_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_skulsr_partial import build,OUT
INPUTS=[]
def fixture(policy,health=4700):
 p=json.loads((OUT/f'skulsr.{policy}.partial.json').read_bytes())
 p['entities'] += [{'id':'unit/target','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'def':100,'mres':0,'block_count':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}},
 {'id':'unit/director','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100,'atk':0}},'resources':{'hp':{'initial':100,'capacity':100}},'spatial':{},'abilities':['ability/wound','ability/restore']}}]
 p['selectors'].append({'id':'selector/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
 p['abilities'] += [{'id':'ability/wound','kind':'ability','selector':'selector/boss','activation':{'mode':'manual','on_start':[{'op':'modify_resource','resource':'hp','value':health}]},'timeline':[]},{'id':'ability/restore','kind':'ability','selector':'selector/boss','activation':{'mode':'manual','on_start':[{'op':'modify_resource','resource':'hp','value':10500}]},'timeline':[]}]
 p['scenarioDraft']={'id':'scenario/skulsr/'+policy,'ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':8},'initialEntities':[{'definition':'unit/skulsr_partial','instanceAlias':'boss','position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':7},'checkpoints':[]}},{'definition':'unit/target','instanceAlias':'target','position':{'row':0,'col':1}},{'definition':'unit/director','instanceAlias':'director','position':{'row':1,'col':7}}],'waves':[]}
 return p
def make(p):
 raw=json.dumps(p,sort_keys=True,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'seed':2802,'document':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=2802)
def cmd(s,who,ability,t):s.submit({'action':'skill','source':who,'ability':ability},at=t)
def exact(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

@pytest.mark.parametrize('policy,mode,damage',[('serialized',0,900),('DB',1,1400)])
def test_unresolved_4700_health_policies_differ_and_combat_f53_has_no_attachment(policy,mode,damage):
 s=make(fixture(policy));cmd(s,'director','ability/wound',1);cmd(s,'boss',f'ability/skulsr_combat_{mode}',2);s.advance(56)
 assert s.ctx.resources.current('boss','mode')==mode
 assert s.ctx.spatial.blocked_by('boss')==s.session.world.resolve('target')
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(55,damage)]
 assert not [e for e in s.session.events if e['type']=='buff.applied' and e['payload'].get('buff')=='buff/chapter02/skulsr_defdown'];exact(s)

def test_attack_dual_signals_source_scale_and_attachment_after_first_damage():
 s=make(fixture('serialized'));cmd(s,'boss','ability/skulsr_attack_0',0);s.advance(24)
 hits=[e for e in s.session.events if e['type']=='damage.accepted']
 # f14/f17 +6 ticks one-cell speed5 flight. atkScale exact float32 .25999999.
 assert [e['time'] for e in hits]==[20,23]
 assert [e['payload']['amount'] for e in hits]==pytest.approx([159.99999046325684,209.99999046325684])
 assert len([e for e in s.session.events if e['type']=='attack.accepted'])==1
 assert len([e for e in s.session.events if e['type']=='projectile.hit'])==2;exact(s)

def test_mode1_attack_then_restore_no_native_dispatch_claim():
 s=make(fixture('serialized',health=4200));cmd(s,'director','ability/wound',1);cmd(s,'boss','ability/skulsr_attack_1',2);cmd(s,'director','ability/restore',30);s.advance(31)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[22,25]
 assert [e['payload']['amount'] for e in hits]==pytest.approx([289.99998569488525,339.99998569488525])
 assert s.ctx.resources.current('boss','mode')==0;exact(s)

def test_old_mode_guard_is_rejected_after_entering():
 s=make(fixture('DB'));cmd(s,'director','ability/wound',1);cmd(s,'boss','ability/skulsr_attack_0',2);s.advance(3)
 rejected=[e for e in s.session.events if e['type']=='command.rejected'];assert len(rejected)==1 and 'condition' in rejected[0]['payload']['reason'];exact(s)

def test_profiles_exact_explicit_and_native_gate_remains_closed():
 for policy in ('serialized','DB'):
  assert (OUT/f'skulsr.{policy}.partial.json').read_bytes()==(json.dumps(build(policy,'damage_then_attachment'),ensure_ascii=False,indent=2)+'\n').encode()
  with pytest.raises(ValueError,match='unresolved'):build(policy,'damage_then_attachment',require_native=True)
 with pytest.raises(ValueError,match='explicit'):build(None,'damage_then_attachment')
 with pytest.raises(ValueError,match='explicit'):build('serialized',None)
