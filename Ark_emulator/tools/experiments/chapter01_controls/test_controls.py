"""Independent source/control probes in the frozen explicit M12 runtime."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BOOT = """
from tools.build_chapter01_controls import *
identity=runtime(RUNTIME)
reference,package=build()
from ark_sim import Compiler,Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
"""


def probe(body):
    result = subprocess.run([sys.executable, "-c", BOOT+body], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout+result.stderr


def test_complete_source_counts_flags_and_predefines_preserved():
    probe("""
assert reference['stages']['level_main_01-11']['native_control_counts']=={'STORY':2,'PREVIEW_CURSOR':1,'ACTIVATE_PREDEFINED':1,'DISPLAY_ENEMY_INFO':3}
assert reference['stages']['level_main_01-12']['native_control_counts']=={'STORY':1,'DISPLAY_ENEMY_INFO':2}
a=reference['stages']['level_main_01-11']['controls'][0]
assert a['native_action']['blockFragment'] is True and a['effects'] is None
assert len(reference['stages']['level_main_01-11']['native_level_document']['predefines']['characterCards'])==12
p=reference['stages']['level_main_01-12']['native_level_document']['predefines']
assert p['characterCards']=={} and len(p['tokenInsts'])==1
t=p['tokenInsts'][0];assert t['inst']['characterKey']=='trap_002_emp' and t['inst']['level']==10
assert t['position']=={'row':2,'col':5} and t['direction']=='UP' and t['hidden'] is False and t['alias'] is None
for level in LEVELS:
 try:require_complete(reference,level)
 except ControlModelGap:pass
 else:raise AssertionError('fake complete control timeline accepted')
""")


def test_UI_text_is_metadata_and_no_native_finished_signal():
    probe("""
story=reference['stories']['obt/tutorial/level/main_01-11_b']
assert story['declared_delay_total']==18
assert [r['headless_model_offset_seconds'] for r in story['classified_rows'] if r['command']=='PopupDialog']==[0,4,8,12,16]
header=next(r for r in story['classified_rows'] if r['command']=='HEADER')
assert header['decoded_parameters']=={'is_skippable':False,'is_autoable':False,'is_tutorial':True}
s=Engine.create(Compiler().compile(fixture(package,story_profile(story))));s.advance(541)
popups=[e for e in s.session.events if e['type']=='chapter01.headless_story.command_observed' and e['payload']['native_row']['command']=='PopupDialog']
assert [e['time'] for e in popups]==[0,120,240,360,480]
assert not [e for e in s.session.events if e['type'] in ['story.finished','native.story.finished']]
assert all(e['payload']['native_command_completed'] is False for e in popups)
assert not [e for e in s.session.events if e['type']=='damage.accepted']
""")


def test_input_lock_effect_phase_boundary_and_recorded_replay():
    probe("""
story=reference['stories']['obt/tutorial/level/main_01-11_b']
s=Engine.create(Compiler().compile(fixture(package,story_profile(story))));s.advance(540)
s.submit({'action':'skill','source':'driver','ability':PING});s.advance(1)
assert any(e['type']=='command.rejected' and 'input locked' in e['payload']['reason'] for e in s.session.events)
assert not s.ctx.state().get('input_locks')
s.submit({'action':'skill','source':'driver','ability':PING});s.advance(1)
assert len([e for e in s.session.events if e['type']=='command.accepted'])==1
assert first_difference(s.snapshot(),replay(s.program,s.export_replay()).snapshot()) is None
""")


def test_illegal_lock_parameter_rejected_at_compile():
    probe("""
for key,value in [('enabled','false'),('key','')]:
 options={'key':'probe','enabled':True};options[key]=value
 try:Compiler().compile(fixture(package,[{'op':'input_lock','target':'battle','parameters':options}]))
 except ValueError:pass
 else:raise AssertionError('bad input lock accepted')
""")


def test_display_repeat_delivery_preserves_route_placeholder_and_flags():
    probe("""
item=next(i for i in reference['control_inventory'] if i['level']=='level_main_01-11' and i['native_action']['actionType']=='DISPLAY_ENEMY_INFO')
a=item['native_action'];assert a['count']==3 and a['interval']==12 and a['routeIndex']==16
assert item['native_route']['motionMode']=='E_NUM'
p=fixture(package,[]);p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions']=[
 {'kind':'effects','delay_seconds':4,'count':3,'interval_seconds':12,'effects':item['effects']}]
s=Engine.create(Compiler().compile(p));s.advance(841)
events=[e for e in s.session.events if e['type']=='chapter01.control.metadata_observed']
assert [e['time'] for e in events]==[120,480,840]
assert all(e['payload']['native_UI_render_or_action_completion'] is False for e in events)
assert all(e['payload']['native_action']['managedByScheduler'] is True for e in events)
""")


def test_activation_is_absence_then_one_birth_no_dormant_route_or_cards():
    probe("""
item=next(i for i in reference['control_inventory'] if i['native_action']['actionType']=='ACTIVATE_PREDEFINED')
assert item['predefine']['hidden'] is True and item['predefine']['alias'] is None
assert item['native_route']['motionMode']=='E_NUM'
s=Engine.create(Compiler().compile(fixture(package,item['effects'],2.99)));s.advance(90)
assert not [e for e in s.session.world.entities() if e['definition_id']==NPC_UNIT]
cp=s.checkpoint();s.advance(1);r=Engine.restore(s.program,cp);r.advance(1)
born=[e for e in s.session.world.entities() if e['definition_id']==NPC_UNIT]
assert len(born)==1
assert born[0]['components']['attributes']['base']['atk']==199
assert born[0]['components']['attributes']['base']['def']==74
assert not born[0]['components']['spatial'].get('route') and not born[0]['components']['runtime'].get('route_hidden')
assert born[0]['components']['runtime']['deployed'] is False # model creation, not native deployed-state proof
assert first_difference(s.snapshot(),r.snapshot()) is None
assert first_difference(s.snapshot(),replay(s.program,s.export_replay()).snapshot()) is None
""")
