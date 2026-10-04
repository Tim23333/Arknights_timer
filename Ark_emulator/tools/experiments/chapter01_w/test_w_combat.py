"""Independent content probes in a fresh pinned runtime subprocess.

Not part of the frozen historical M8 suite. No candidate/primary core mutation.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BOOT = """
from tools.build_chapter01_w_combat import runtime,RUNTIME,EXPECTED,build,fixture,NORMAL,C4
identity=runtime(RUNTIME,EXPECTED)
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
assert implementation_digest()==EXPECTED
"""


def probe(code):
    result = subprocess.run([sys.executable, "-c", BOOT+code], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout+result.stderr


def test_native_binding_and_strict_profile():
    probe("""
source,p=build()
assert len(source['normal_modes'])==2
for row in source['normal_modes']:
 assert row['combat_source']['native_class']=='RangedAttack'
 assert [e['frame'] for e in row['mode_source']['attack_animation']['events']]==[9,23]
assert source['method_bodies_recovered'] is False
assert p['manifest']['metadata']['full_enemy_implemented'] is False
try: build('native_two_shots_proven')
except ValueError: pass
else: raise AssertionError('unknown/unproved profile accepted')
""")


def test_alternative_first_signal_is_actually_one_packet():
    probe("""
_,p=build('first_signal_only_model')
s=Engine.create(Compiler().compile(fixture(p)));s.advance(30)
assert s.ctx.resources.current('target0','hp')==4630
launches=[e for e in s.session.events if e['type']=='projectile.launched']
assert [e['time'] for e in launches]==[9]
assert [e['time'] for e in s.session.events if e['type']=='damage.accepted']==[15]
""")


def test_independent_DEF_formula_in_both_modes():
    probe("""
_,p=build()
for mode in (0,1):
 data=fixture(p,phase=mode)
 data['entities'][1]['components']['attributes']['base']['def']=250
 s=Engine.create(Compiler().compile(data));s.advance(30)
 assert s.ctx.resources.current('target0','hp')==4560 # 5000-2*(470-250)
 damage=[e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']
 assert damage==[220,220]
""")


def test_range_and_motion_no_implicit_target_bypass():
    probe("""
_,p=build()
data=fixture(p,positions=((3,6),)) # distance3 > source2.5
s=Engine.create(Compiler().compile(data));s.advance(45)
assert not [e for e in s.session.events if e['type']=='projectile.launched']
data=fixture(p)
data['entities'][1]['tags']=['player','air']
s=Engine.create(Compiler().compile(data));s.advance(45)
assert not [e for e in s.session.events if e['type']=='projectile.launched']
data=fixture(p,positions=((3,4),(3,5)))
s=Engine.create(Compiler().compile(data));s.advance(10)
s.submit({'action':'withdraw','source':'target0'});s.advance(25)
assert s.ctx.resources.current('target1','hp')==5000 # captured target invalid: no retarget to living candidate
assert not [e for e in s.session.events if e['type']=='damage.accepted']
""")


def test_automatic_C4_clock_still_20seconds_and_stops_launches():
    probe("""
_,p=build(); data=fixture(p,automatic_c4=True)
data['entities'][1]['components']['resources']['hp'].update(initial=50000,capacity=50000)
data['entities'][1]['components']['attributes']['base']['max_hp']=50000
s=Engine.create(Compiler().compile(data));s.advance(870)
starts=[e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==C4+'0']
assert starts==[269,869],starts
launches=[e['time'] for e in s.session.events if e['type']=='projectile.launched']
assert not [t for t in launches if 269<=t<=383],launches
assert any(383<t<869 for t in launches)
""")


def test_HP_death_uses_actual_lifecycle_and_launched_packet_policy():
    probe("""
_,p=build()
for victim,expected in [('w',4630),('target0',0)]:
 data=fixture(p)
 aid='ability/w_test_lethal_resource'
 data['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual','on_start':[
  {'op':'modify_resource','target':'source','resource':'hp','value':0}]},'parameters':{'blocks_attacks':False},'timeline':[]})
 index=0 if victim=='w' else 1
 data['entities'][index]['components'].setdefault('abilities',[]).append(aid)
 s=Engine.create(Compiler().compile(data));s.advance(10)
 s.submit({'action':'skill','source':victim,'ability':aid});s.advance(25)
 assert not s.ctx.alive(victim)
 assert s.ctx.resources.current('target0','hp')==expected
 assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1
 assert any(e['type']=='entity.died' and e['payload']['target']==s.session.world.resolve(victim) for e in s.session.events)
""")
