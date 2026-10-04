"""Actual-source lasso and generic owned attachment boundaries."""
from pathlib import Path
from copy import deepcopy
import json,sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m78_owned_attachment_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]


def fixture(second=False,flags=(),caster_flags=(),hp=10000,res=0):
    p=json.loads((ROOT/'packages/campaign/chapter04_dmage/module.reference.json').read_bytes())
    uid=p['entities'][0]['id'];p['entities'][0]['components']['selection_state']['abnormal_flags']=list(caster_flags)
    target={'id':'unit/target','kind':'entity','tags':['player','ground'],'components':{
        'attributes':{'base':{'max_hp':hp,'atk':0,'def':0,'mres':res,'attack_interval':1,'attack_speed_ratio':1,'move_speed':1,'block_count':0}},
        'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1,'abnormal_flags':list(flags)},
        'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'spatial':{},'abilities':[],
        'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    p['entities'].append(target)
    initial=[{'definition':uid,'instanceAlias':'caster','position':{'row':1,'col':1}},
        {'definition':'unit/target','instanceAlias':'victim','position':{'row':1,'col':3}}]
    if second:initial.append({'definition':'unit/target','instanceAlias':'newest','position':{'row':2,'col':3}})
    p['scenarioDraft']={'id':'scene/dmage_probe','ruleset':'ruleset/ark_standard','objectives':{},
        'map':{'rows':4,'cols':8},'initialEntities':initial}
    INPUTS.append(p)
    return p

def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=78022)
def events(s,kind):return [thaw(e) for e in s.session.events if e['type']==kind]
def attachment(s):return next(iter(s.ctx.attachments.state()['instances'].values()))
def aid(s):return next(a['id'] for a in s.program.definitions.values() if a.get('kind')=='ability' and a.get('wait_for_channels'))


def test_source_priority_one_charge_begin26_flight10_contact32_and_no_normal_attack():
    s=make();s.session.advance(33)
    started=events(s,'ability.started')
    assert len(started)==1 and started[0]['payload']['ability']==aid(s)
    assert s.ctx.resources.current('caster','lasso_uses')==0
    assert events(s,'attachment.started')[0]['time']==26
    assert events(s,'attachment.reached')[0]['time']==32
    assert attachment(s)['state']=='held' and attachment(s)['held_until']==632
    assert s.ctx.resources.current('victim','hp')==pytest.approx(10000-500*.35/30)
    assert not events(s,'attack.accepted')
    assert s.ctx.buffs.controls('victim')=={'move':False,'attack':False,'abilities':False,'block':False}


def test_infinite_target_stun_no_expiry_gap_at_one_second_refresh():
    s=make();s.session.advance(62)
    rows=s.ctx.get('victim',('buffs','instances'))
    assert len(rows)==1 and rows[0]['expires_at'] is None
    assert s.ctx.buffs.controls('victim')['move'] is False
    s.session.advance(1)
    renewed=s.ctx.get('victim',('buffs','instances'))
    assert len(renewed)==1 and renewed[0]['id']==rows[0]['id'] and renewed[0]['generation']==rows[0]['generation']+1
    assert renewed[0]['expires_at'] is None and s.ctx.buffs.controls('victim')['block'] is False
    assert [e['time'] for e in events(s,'attachment.refreshed')]==[32,62]


def test_source_silence_cancel_same_tick_clears_both_owned_leases():
    s=make();s.session.advance(60)
    assert s.ctx.get('caster',('buffs','instances')) and s.ctx.get('victim',('buffs','instances'))
    s.ctx.set('caster',('selection_state','abnormal_flags'),[12])
    s.session.advance(1)
    assert not attachment(s)['active'] and attachment(s)['reason']=='source_flags'
    assert s.ctx.buffs.controls('victim')=={'move':True,'attack':True,'abilities':True,'block':True}
    assert not s.ctx.get('caster',('runtime','casts'))
    assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.attachment.step']


def test_real_source_retire_clears_owned_target_immediately_not_at_next_tick():
    s=make();s.session.advance(40)
    s.ctx.lifecycle.retire('caster','dead')
    assert not attachment(s)['active']
    assert s.ctx.get('victim',('buffs','instances'))==[]
    assert s.ctx.buffs.controls('victim')['attack'] is True
    assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.attachment.step']


def test_public_interrupt_during_windup_cleans_self_owned_hold():
    s=make();s.session.advance(5)
    assert s.ctx.buffs.controls('caster')['move'] is False
    s.ctx.abilities.interrupt('caster','test_interrupt',ability_ids=[aid(s)])
    assert s.ctx.buffs.controls('caster')['move'] is True
    assert s.ctx.get('caster',('buffs','instances'))==[] and s.ctx.attachments.state()['instances']=={}
    assert s.ctx.resources.current('caster','lasso_uses')==0


def test_native_postfilter12_stun_exclusion_vs_basic4_and_newest_priority():
    s=make(fixture(second=True,flags=[0]));s.session.advance(1)
    assert events(s,'ability.started')[0]['payload']['targets']==[s.session.world.resolve('newest')]
    s=make(fixture(flags=[0]));s.session.advance(1)
    assert not events(s,'attachment.started')
    assert s.ctx.resources.current('caster','lasso_uses')==1
    assert events(s,'ability.started')[0]['payload']['ability']!=aid(s)


def test_init_silence_does_not_spend_charge_can_activate_after_status_removed():
    s=make(fixture(caster_flags=[12]));s.session.advance(2)
    assert s.ctx.resources.current('caster','lasso_uses')==1
    s.ctx.set('caster',('selection_state','abnormal_flags'),[])
    s.session.advance(1)
    assert any(e['payload']['ability']==aid(s) for e in events(s,'ability.started'))
    assert s.ctx.resources.current('caster','lasso_uses')==0


def test_live_at_hit_source_attack_and_target_res_during_integral():
    s=make();s.session.advance(33)
    old=s.ctx.resources.current('victim','hp')
    s.ctx.set('caster',('attributes','base','atk'),1000)
    s.ctx.set('victim',('attributes','base','mres'),50)
    s.session.advance(1)
    assert old-s.ctx.resources.current('victim','hp')==pytest.approx(1000*.35/30*.5)


def test_actual_ordered_checkpoint_mid_flight_and_held_resume_public_replay(tmp_path):
    s=make();s.session.advance(28)
    cp=tmp_path/'flight.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
    s.session.advance(70);r.session.advance(70)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
    cp=tmp_path/'held.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
    s.session.advance(10);r.session.advance(10)
    assert s.checkpoint()==r.checkpoint()


def test_natural_end_half_open600_integral_packets_exact20s_and_recovery21():
    s=make();s.session.advance(632)
    assert attachment(s)['active'] and attachment(s)['packets']==600
    assert s.ctx.resources.current('victim','hp')==pytest.approx(6500,abs=1e-7)
    assert s.ctx.buffs.controls('victim')['abilities'] is False
    s.session.advance(1)
    assert attachment(s)['active'] is False and attachment(s)['reason']=='complete'
    assert s.ctx.buffs.controls('victim')['abilities'] is True
    assert s.ctx.buffs.controls('caster')['move'] is False
    s.session.advance(21)
    assert len([e for e in events(s,'ability.started') if e['payload']['ability']==aid(s)])==1
    assert s.ctx.buffs.controls('caster')['move'] is True


def test_target_retire_breaks_link_and_clears_owned_leases_same_tick():
    s=make();s.session.advance(40)
    s.ctx.lifecycle.retire('victim','withdrawn')
    assert not attachment(s)['active'] and attachment(s)['reason']=='target_invalid'
    assert s.ctx.get('victim',('buffs','instances'))==[]
    assert not s.ctx.get('caster',('runtime','casts'))
    assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.attachment.step']


def test_target_cleanse_can_act_until_exact_next_refresh_without_fake_expiry():
    s=make();s.session.advance(61)
    buff=attachment(s)['owned_buffs'][-1]
    s.ctx.buffs.remove('victim',buff)
    assert s.ctx.buffs.controls('victim')['move'] is True
    s.session.advance(1)
    assert s.ctx.buffs.controls('victim')['move'] is True # frame61, refresh is frame62.
    s.session.advance(1)
    assert s.ctx.buffs.controls('victim')['move'] is False
    assert s.ctx.get('victim',('buffs','instances'))[0]['expires_at'] is None


def test_force_reach_timeout_raw_true_vs_explicit_false_policy():
    for force in (True,False):
        p=fixture();d=p['definitions'][0];d['motion']['parameters']['speed']=0
        d['flight_lifetime_seconds']=.1;d['force_reach_on_timeout']=force
        s=make(p);s.session.advance(31)
        x=attachment(s)
        if force:assert x['active'] and x['state']=='held' and x['position']['col']==3
        else:assert not x['active'] and x['reason']=='flight_timeout'


@pytest.mark.parametrize('ignore,expected',[(False,1),(True,0)])
def test_explicit_buff_damage_sp_switch_and_no_attack_sp(ignore,expected):
    p=fixture();p['definitions'][0]['effect']['damage_flags']['ignore_for_sp']=ignore
    p['entities'][1]['components']['resources']['sp']={'initial':0,'capacity':10,
        'recovery_rule':'rule/target_sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}
    p['rules'].append({'id':'rule/target_sp','kind':'rule','contract':'resource.recovery',
        'implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}})
    s=make(p);s.session.advance(33)
    assert s.ctx.resources.current('victim','sp')==expected
    accepted=events(s,'damage.accepted')[-1]['payload']
    assert accepted['damage_flags']=={'source_attack_type':'BUFF','ignore_for_sp':ignore}
    assert not events(s,'attack.accepted')


def test_own_source_stun_exception_does_not_hide_cast_owned_silence():
    p=fixture();p['buffs'].append({'id':'buff/self_silence','kind':'buff','selection_flags':{'abnormal_flags':[12]}})
    p['abilities'][0]['activation']['on_start'].append({'op':'apply_buff','target':'source','buff':'buff/self_silence','bind_to_cast':True})
    s=make(p);s.session.advance(28)
    assert not attachment(s)['active'] and attachment(s)['reason']=='source_flags'


def test_step_after_damage_hook_error_atomic_stores_and_binding_refresh(monkeypatch):
    p=fixture();p['entities'][1]['components']['buffs']={'initial':['buff/failure']}
    p['buffs'].append({'id':'buff/failure','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/failure',
        'samples':{'stream':'attachment_failure','count':1}}]})
    p['rules'].append({'id':'rule/failure','kind':'rule','contract':'damage.pipeline',
        'implementation':{'type':'graph','nodes':[{'id':'bad','expression':"{'accepted':True,'amount':1/0,'allocations':[],'events':[]}"}],'output':'nodes.bad'}})
    s=make(p);captured=[];original=s.ctx.attachments.step
    def wrapper(session,payload):
        captured.append({'world':session.world.snapshot(),'scheduler':session.scheduler.snapshot(),
            'random':session.random.snapshot(),'events':session._events.snapshot()})
        return original(session,payload)
    s.session._handlers['domain.attachment.step']=wrapper
    with pytest.raises(Exception):s.session.advance(33)
    after={'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),
        'random':s.session.random.snapshot(),'events':s.session._events.snapshot()}
    assert after==captured[-1]
    assert s.ctx.get('victim',('buffs','instances'))[0]['definition']=='buff/failure'


def test_inactive_target_during_windup_ends_without_stuck_source_hold():
    s=make();s.session.advance(5)
    s.ctx.lifecycle.retire('victim','withdrawn');s.session.advance(24)
    assert s.ctx.attachments.state()['instances']=={} and not s.ctx.get('caster',('runtime','casts'))
    assert s.ctx.get('caster',('buffs','instances'))==[] and s.ctx.buffs.controls('caster')['move']


@pytest.mark.parametrize('field,value',[('completion_blocking',1),('source_cancel_flags',[46]),
    ('ignored_owned_source_flags',[True]),('force_reach_on_timeout',None),('step_interval_seconds',0),
    ('max_packets',-1),('duration_seconds',float('nan'))])
def test_bad_generic_profile_rejected(field,value):
    p=fixture();p['definitions'][0][field]=value
    with pytest.raises(ValueError):Compiler().compile(p)


@pytest.mark.parametrize('blocking',[False,True])
def test_explicit_completion_blocking_policy_and_terminal_owned_cleanup(blocking):
    p=fixture();p['entities'][0]['tags']=['player'] # A generic non-enemy source keeps the link alive.
    p['definitions'][0]['completion_blocking']=blocking
    p['scenarioDraft']['objectives']={'type':'waves'}
    p['scenarioDraft']['waves']=[{'at':10000,'definition':'unit/target','position':{'row':3,'col':7}}]
    s=make(p);s.session.advance(40);s.ctx.state_update(pending_waves=0)
    s.ctx.lifecycle.tick(s.session)
    assert s.ctx.state()['finished'] is (not blocking)
    if not blocking:
        assert not attachment(s)['active'] and attachment(s)['reason']=='battle_terminal'
        assert s.ctx.buffs.controls('victim')['move']
    else:
        s.ctx.attachments.stop(attachment(s)['id'],'complete');s.ctx.lifecycle.tick(s.session)
        assert s.ctx.state()['finished']


def test_duplicate_owned_step_payload_cannot_deliver_or_refresh_twice():
    s=make();s.session.advance(33)
    task=next(t for t in s.session.scheduler.pending if t['kind']=='domain.attachment.step')
    s.session.schedule(task['kind'],task['payload'],task['at'],phase=task['phase'],priority=-1)
    s.session.advance(1)
    assert attachment(s)['packets']==2
    assert len(events(s,'attachment.refreshed'))==1


def test_terminal_owned_buff_callback_failure_restores_goal_link_rng_tasks_and_events():
    p=fixture();p['entities'][0]['tags']=['player']
    p['definitions'][0]['completion_blocking']=False
    p['scenarioDraft']['objectives']={'type':'waves'}
    p['scenarioDraft']['waves']=[{'at':10000,'definition':'unit/target','position':{'row':3,'col':7}}]
    target_buff=next(b for b in p['buffs'] if b['id']==p['definitions'][0]['target_buff'])
    target_buff['on_remove']=[{'op':'random','stream':'owned_cleanup_failure','on_success':[
        {'op':'modify_resource','resource':'missing','delta':1}]}]
    s=make(p);s.session.advance(40);s.ctx.state_update(pending_waves=0)
    before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.lifecycle.tick(s.session)
    assert s.checkpoint()==before and not s.ctx.state()['finished'] and attachment(s)['active']


def test_undeclared_channel_waiting_and_bad_actor_damage_flags_compile_rejected():
    p=fixture();p['abilities'][0]['wait_for_channels']=False
    with pytest.raises(ValueError,match='wait_for_channels'):Compiler().compile(p)
    p=fixture();p['definitions'][0]['effect']['damage_flags']['ignore_for_sp']=1
    with pytest.raises(ValueError,match='damage_flags'):Compiler().compile(p)


def test_direct_explicit_damage_flags_and_orphan_buff_binding_fail_without_writes():
    s=make();before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.effects.execute('caster',['victim'],{'op':'damage',
        'damage_flags':{'source_attack_type':'BUFF','ignore_for_sp':1}})
    with pytest.raises(ValueError):s.ctx.effects.execute('caster',['victim'],{'op':'apply_buff',
        'buff':s.program.definitions[next(x for x in s.program.definitions if x.startswith('attachment/'))]['target_buff'],
        'bind_to_cast':True})
    assert s.checkpoint()==before
