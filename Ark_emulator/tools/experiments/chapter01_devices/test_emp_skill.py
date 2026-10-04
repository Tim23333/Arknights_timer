"""Independent EMP resource, target, stun, cast-end and retirement boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m15_device_candidate'
sys.path.insert(0,str(RUNTIME))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay


def scene(enemies=True,dp=50):
    p=json.loads((ROOT/'packages/campaign/chapter01_devices/emp.partial.json').read_bytes())
    p['scenarioDraft']['resources']['dp']['initial']=dp
    if enemies:
        p['entities'].append({'id':'unit/emp_probe_enemy','kind':'entity','tags':['enemy','ground'],
            'components':{'attributes':{'base':{'max_hp':2000,'atk':1000,'def':50,'mres':20}},'spatial':{},
                'resources':{'hp':{'initial':2000,'capacity':2000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},
                'abilities':['ability/emp_probe_arts','ability/emp_probe_physical','ability/emp_probe_true']}})
        p['entities'].append({'id':'unit/emp_probe_air','kind':'entity','tags':['enemy','flying'],
            'components':{'attributes':{'base':{'max_hp':2000}},'spatial':{},
                'resources':{'hp':{'initial':2000,'capacity':2000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
        for alias,point,definition in [('near1',(5,6),'unit/emp_probe_enemy'),('near2',(4,5),'unit/emp_probe_enemy'),
                ('far',(5,7),'unit/emp_probe_enemy'),('air',(5,6),'unit/emp_probe_air')]:
            p['scenarioDraft']['initialEntities'].append({'definition':definition,'instanceAlias':alias,'position':{'row':point[0],'col':point[1]}})
        p['selectors'].append({'id':'selector/emp_probe_device','kind':'selector','region':{'type':'all'},'filters':[{'tag':'device'},{'state':'alive'}],'limit':1})
        for kind in ('arts','physical','true'):
            p['abilities'].append({'id':'ability/emp_probe_'+kind,'kind':'ability','activation':{'mode':'manual'},
                'selector':'selector/emp_probe_device','timeline':[{'at':0,'effect':{'op':'damage','damage_type':kind}}]})
    return p


def make(data=None):return Engine.create(Compiler().compile(data or scene()),seed=1315)
def emp(s):return next(e['id'] for e in s.session.world.entities() if e['definition_id']=='unit/chapter01_emp')
def events(s,kind):return [e for e in s.session.events if e['type']==kind]
def roundtrip(s):
    cp=s.checkpoint();restored=Engine.restore(s.program,cp);s.advance(2);restored.advance(2)
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_actual_stats_predefine_coords_alias_null_and_sp_five_seconds():
    s=make(scene(False));uid=emp(s)
    assert s.ctx.get(uid,('spatial','position'))=={'row':5,'col':5}
    assert s.ctx.resources.current(uid,'hp')==100 and s.ctx.resources.current(uid,'sp')==0
    # The declared periodic driver counts tick0: five complete30-tick periods
    # settle at29/59/89/119/149. Command phase can use the fifth at150.
    s.advance(149);assert s.ctx.resources.current(uid,'sp')==4
    s.advance(1);assert s.ctx.resources.current(uid,'sp')==5
    roundtrip(s)


def test_true_two_targets_packet_23_stun_210_and_after_finished_retire():
    s=make();uid=emp(s);s.submit({'action':'skill','source':uid,'ability':'ability/chapter01_emp/burst'},at=151)
    s.advance(174);assert not events(s,'damage.accepted') # 151 +ceil(.75*30)=174, exclusive end
    s.advance(1)
    hits=events(s,'damage.accepted');assert [e['time'] for e in hits]==[174,174]
    assert {e['payload']['target'] for e in hits}=={s.session.world.resolve('near1'),s.session.world.resolve('near2')}
    assert [e['payload']['amount'] for e in hits]==[800,800]
    assert s.ctx.resources.current('near1','hp')==1200 and s.ctx.resources.current('far','hp')==2000 and s.ctx.resources.current('air','hp')==2000
    assert s.ctx.buffs.controls('near1')['move'] is False
    assert s.ctx.resources.current('system/battle','dp')==40 and s.ctx.resources.current(uid,'sp')==0
    s.advance(22);assert not s.ctx.alive(uid)
    ended=events(s,'ability.finished');died=events(s,'entity.died')
    assert len(ended)==len(died)==1 and ended[0]['time']==died[0]['time']==196 and ended[0]['id']<died[0]['id']
    assert s.ctx.resources.current(uid,'hp')==100 and s.ctx.state()['kills']==0
    s.advance(186);assert s.ctx.buffs.controls('near1')['move'] is False # tick383 before174+210 expiry
    s.advance(1);assert s.ctx.buffs.controls('near1')['move'] is True
    roundtrip(s)


@pytest.mark.parametrize('kind',['arts','physical','true'])
def test_passive_invincible_rejects_real_damage_in_all_channels(kind):
    s=make();uid=emp(s);s.submit({'action':'skill','source':'near1','ability':'ability/emp_probe_'+kind});s.advance(1)
    assert s.ctx.resources.current(uid,'hp')==100
    assert len(events(s,'damage.rejected'))==1 and not events(s,'damage.accepted')
    roundtrip(s)


@pytest.mark.parametrize('when,dp',[(0,50),(151,9)])
def test_sp_or_dp_failure_is_atomic_and_device_remains(when,dp):
    s=make(scene(False,dp));uid=emp(s);s.submit({'action':'skill','source':uid,'ability':'ability/chapter01_emp/burst'},at=when);s.advance(when+1)
    assert s.ctx.alive(uid) and len(events(s,'command.rejected'))==1 and not events(s,'ability.started')
    assert s.ctx.resources.current('system/battle','dp')==dp
    if when:assert s.ctx.resources.current(uid,'sp')==5
    roundtrip(s)


def test_empty_target_cast_pays_and_finishes_then_retires_once():
    s=make(scene(False));uid=emp(s)
    s.submit({'action':'skill','source':uid,'ability':'ability/chapter01_emp/burst'},at=151)
    s.submit({'action':'skill','source':uid,'ability':'ability/chapter01_emp/burst'},at=200);s.advance(201)
    assert not s.ctx.alive(uid) and s.ctx.resources.current('system/battle','dp')==40
    assert not events(s,'damage.accepted') and len(events(s,'entity.died'))==1 and len(events(s,'command.rejected'))==1
    roundtrip(s)


@pytest.mark.parametrize('parameters',[{},None,{'reason':''},{'reason':'bad.reason'},{'reason':7}])
def test_retirement_requires_explicit_valid_reason(parameters):
    p=scene(False);p['abilities'][0]['events'][0]['effects'][0]['parameters']=parameters
    with pytest.raises(ValueError):Compiler().compile(p)


def test_battle_retirement_preflight_rejected():
    p=scene(False);p['abilities'][0]['events'][0]['effects'][0]['target']='battle'
    with pytest.raises(ValueError,match='reserved battle'):Compiler().compile(p)
