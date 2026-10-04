"""Independent selected-NPC-skill probes, fresh candidate subprocess per case."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BOOT = """
from tools.build_chapter01_predefined_skill import runtime,RUNTIME,EXPECTED,build,fixture,SKILL,BUFF
runtime(RUNTIME,EXPECTED)
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference
"""


def probe(code):
    result = subprocess.run([sys.executable, "-c", BOOT+code], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout+result.stderr


def test_exact_manual_source_and_no_clock_reset_claim():
    probe("""
src,p=build();level=src['selected_level']
assert level['skillType']=='MANUAL' and level['duration']==20
assert level['spData']['spCost']==50 and level['spData']['initSp']==0
assert level['blackboard']==[{'key':'atk','value':.1,'valueStr':None}]
a=next(a for a in p['abilities'] if a['id']==SKILL)
assert not a['activation'].get('parameters',{}).get('reset_attack_clock')
assert src['selected_skill_prefab_sources']=={} and src['full_NPC_implemented'] is False
assert len(src['native_cards'])==12 and src['native_config']['hidden'] is True
""")


def test_real_init_zero_earns50_and_normal_cast_does_not_freeze():
    probe("""
_,p=build();s=Engine.create(Compiler().compile(fixture(p,initial_sp=0)))
s.advance(1499);assert s.ctx.resources.current('npc','sp')==49
s.advance(1);assert s.ctx.resources.current('npc','sp')==50
_,p=build();s=Engine.create(Compiler().compile(fixture(p,initial_sp=0)))
s.advance(31);assert s.ctx.resources.current('npc','sp')==1
assert any(e['type']=='ability.started' for e in s.session.events)
""")


def test_independent_fractional_ATK_and_DEF():
    probe("""
_,p=build();data=fixture(p)
data['entities'][1]['components']['attributes']['base']['def']=100
s=Engine.create(Compiler().compile(data));s.submit({'action':'skill','source':'npc','ability':SKILL});s.advance(13)
assert abs(s.ctx.resources.current('enemy','hp')-99881.1)<1e-8 #199*1.1-100=118.9
assert s.ctx.resources.current('npc','sp')==0
""")


def test_positive_active_recovery_suppressed_and_duplicate_rejected():
    probe("""
_,p=build();data=fixture(p)
aid='ability/adnach_probe_SP_grant'
data['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual','on_start':[
 {'op':'modify_resource','target':'source','resource':'sp','delta':5,'parameters':{'respect_recovery_freeze':True}}]},
 'parameters':{'blocks_attacks':False},'timeline':[]})
data['entities'][0]['components']['abilities'].append(aid)
s=Engine.create(Compiler().compile(data));s.submit({'action':'skill','source':'npc','ability':SKILL});s.advance(3)
s.submit({'action':'skill','source':'npc','ability':aid});s.submit({'action':'skill','source':'npc','ability':SKILL});s.advance(10)
assert s.ctx.resources.current('npc','sp')==0
assert len([e for e in s.session.events if e['type']=='command.rejected'])==1
assert abs(s.ctx.resources.current('enemy','hp')-99811.1)<1e-8
assert first_difference(s.snapshot(),replay(s.program,s.export_replay()).snapshot()) is None
""")


def test_live_impact_can_see_skill_start_without_resetting_existing_attack():
    probe("""
_,p=build();s=Engine.create(Compiler().compile(fixture(p)))
s.advance(10);s.submit({'action':'skill','source':'npc','ability':SKILL});s.advance(3)
launches=[e['time'] for e in s.session.events if e['type']=='projectile.launched']
assert launches==[9] # skill at10 neither cancels nor duplicates ordinary launch
damage=[e for e in s.session.events if e['type']=='damage.accepted']
assert len(damage)==1 and damage[0]['time']==12 and abs(damage[0]['payload']['amount']-188.9)<1e-8
assert first_difference(s.snapshot(),replay(s.program,s.export_replay()).snapshot()) is None
""")


def test_one_SP_below_cost_rejects_without_modifier_or_partial_payment():
    probe("""
_,p=build();s=Engine.create(Compiler().compile(fixture(p,initial_sp=49)))
s.submit({'action':'skill','source':'npc','ability':SKILL});s.advance(13)
assert s.ctx.resources.current('npc','sp')==49
assert s.ctx.resources.current('enemy','hp')==99831
assert len([e for e in s.session.events if e['type']=='command.rejected'])==1
assert not [e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==BUFF]
""")
