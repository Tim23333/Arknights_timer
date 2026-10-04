from copy import deepcopy
import pytest
from tools.experiments.chapter06_boss_peer.test_checkpoint_fixture import fixture,make,deploy,skill,ev,capture,exact,ROOT,BOSS,PREFIX

def test_real_normal_ground_packet28_flight3_target_event_SP_once_and_cold_frozen():
 s=make(fixture());deploy(s);s.advance(170);capture(s,'normal_ground_native_packet')
 hits=ev(s,'damage.accepted');assert [e['time'] for e in hits]==[31,142] and [e['payload']['amount'] for e in hits]==pytest.approx([365.2,365.2])
 assert [e['time'] for e in ev(s,'projectile.launched')]==[28,139] and [e['time'] for e in ev(s,'attack.accepted')]==[31,142]
 assert s.ctx.resources.current('tank','sp')==2 and 'sp' not in s.ctx.get('boss',('resources',))
 buffs=s.ctx.get('tank',('buffs','instances'),[]);assert [b['definition'] for b in buffs]==['buff/ch6/cold/e2c_freeze'] and buffs[0]['expires_at']==292
 assert hits[0]['payload']['damage_flags']=={'source_attack_type':'NORMAL','ignore_for_sp':False}

def test_first_frame_source2_realblocker_hard_eligibility_even_extreme_other_taunt():
 p=fixture();p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':8},'checkpoints':[]};p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':8},'checkpoints':[]};s=make(p);deploy(s,row=2,col=2);deploy(s,'other',2,3);s.advance(40);capture(s,'source2_hard_blocker')
 assert s.ctx.get('boss',('runtime','blocked_by'))==6
 assert list(ev(s,'ability.started')[0]['payload']['targets'])==[6] and [e['payload']['target'] for e in ev(s,'damage.accepted')]==[6]

@pytest.mark.parametrize('state',[{'camouflage':True},{'target_free':True}])
def test_unqualified_current_blocker_never_falls_back_to_visible_other(state):
 p=fixture(state);other=next(d for d in p['definitions'] if d['id']=='unit/peer/other');other['components']['selection_state'].update(camouflage=False,target_free=False)
 p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':8},'checkpoints':[]};s=make(p);deploy(s,row=2,col=2);deploy(s,'other',2,3);s.advance(90);capture(s,'blocker_unselectable_'+repr(state))
 assert s.ctx.get('boss',('runtime','blocked_by'))==6 and not ev(s,'ability.started') and not ev(s,'damage.accepted')

def test_no_block_normal_motionone_rejects_air_without_altering_native_skillgate():
 s=make(fixture(tag='flying'));deploy(s);s.advance(90);capture(s,'normal_air_unqualified');assert not ev(s,'ability.started') and not ev(s,'damage.accepted')

def test_initial_source_skill_clocks_typed_and_no_sp_or_fake_summon_branch():
 s=make(fixture());clocks=s.ctx.get('boss',('runtime','cooldowns'));assert clocks[PREFIX+'ice0']==clocks[PREFIX+'ice1']==1050 and clocks[PREFIX+'burst0']==clocks[PREFIX+'burst1']==315
 assert s.ctx.resources.current('boss','summon_uses')==1 and not s.ctx.active('trap_010_frosts#1') and not s.ctx.active('trap_010_frosts#2');s.advance(314);capture(s,'real_initial_clocks_no_targets');assert not [e for e in ev(s,'ability.started') if '/burst' in e['payload']['ability'] or '/ice' in e['payload']['ability']]

def test_hp_zero_firstdown_10s_full_restore_20s_invul_halfopen_second_truekill_disk_head(tmp_path):
 s=make(fixture());skill(s,'hit',5);skill(s,'small',904);skill(s,'small',905);skill(s,'hit',906);s.advance(6)
 assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.get('boss',('runtime','rebirth','count'))==1
 s.advance(300);assert s.ctx.attributes.values('boss')['atk']==660
 exact(s,tmp_path,601);capture(s,'rebirth_invulnerable_truekill')
 assert not s.ctx.alive('boss') and s.ctx.get('boss',('runtime','state'))=='dead'
 changes=[e for e in ev(s,'resource.changed') if e['payload']['target']==2 and e['payload']['resource']=='hp']
 assert any(e['time']==305 and e['payload']['value']==30000 for e in changes)
 assert not [e for e in changes if e['time']==904] and any(e['time']==905 and e['payload']['value']==29900 for e in changes)
 assert len(ev(s,'combat.kill'))==1 and s.ctx.get('boss',('runtime','rebirth','count'))==1

def test_actual_rebirth_priority10_activates_two_original_dormant_traps_once_and_head(tmp_path):
 s=make(fixture());ids=[s.session.world.resolve('trap_010_frosts#1'),s.session.world.resolve('trap_010_frosts#2')];skill(s,'hit',5);s.advance(6);exact(s,tmp_path,340);capture(s,'source_summon_actual_traps')
 assert [s.session.world.resolve('trap_010_frosts#1'),s.session.world.resolve('trap_010_frosts#2')]==ids and all(s.ctx.active(i) for i in ids)
 summons=[e for e in ev(s,'ability.started') if e['payload']['ability']==PREFIX+'summon'];assert len(summons)==1 and summons[0]['time']>=305
 assert s.ctx.resources.current('boss','summon_uses')==0 and s.ctx.get('boss',('runtime','rebirth','count'))==1
 assert all(s.ctx.resources.current(i,'sp')>0 for i in ids)
