"""Actual C6 ordinary FrostNova2 profile, rebirth, Cold/skill/branch author probes."""
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.chapter06_boss.frstar2.build_module import ROOT,OUT,COLD,UID,N,B,I,SUM
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def package(*,target=True,tiles=False):
    p=json.loads((OUT/'model.json').read_bytes())
    p['entities'].append({'id':'unit/test/frstar2/player','kind':'entity','tags':['player','ground','cold_receiver'],'components':{'attributes':{'base':{'max_hp':1000000,'atk':100000,'def':100,'mres':25,'attack_speed_ratio':1,'block_count':0}},'resources':{'hp':{'initial':1000000,'capacity':1000000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/test/frstar2/kill']}})
    p['entities'].append({'id':'unit/test/frstar2/controller','kind':'entity','tags':['test_controller'],'components':{'attributes':{'base':{'max_hp':100,'atk':100000}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/test/frstar2/kill']}})
    p['selectors'].append({'id':'selector/test/frstar2/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/test/frstar2/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/frstar2/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    # Exact source hidden token profiles are integrated by Root; probes use an
    # explicit inert activation witness definition to exercise branch semantics.
    p['entities'].append({'id':'unit/test/frstar2/branch_witness','kind':'entity','tags':['test_branch_witness'],'components':{'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    initial=[{'definition':'unit/test/frstar2/controller','instanceAlias':'controller','position':{'row':4,'col':8}},{'definition':UID,'instanceAlias':'boss','position':{'row':2,'col':2}},*({'definition':'unit/test/frstar2/branch_witness','instanceAlias':key,'position':{'row':2,'col':col},'active':False,'registration_key':key} for key,col in [('trap_010_frosts#1',8),('trap_010_frosts#2',3)])]
    branch={'loop':False,'phases':[{'pre_delay_seconds':0,'actions':[{'delay_seconds':0,'effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':key}}]} for key in ('trap_010_frosts#1','trap_010_frosts#2')]}]}
    scene={'id':'scene/ch6/frstar2/author','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':9},'resources':{'dp':{'initial':30,'capacity':99},'life':{'initial':99999,'capacity':99999}},'initialEntities':initial,'roster':['unit/test/frstar2/player'],'branches':{'frstar_frosts':branch}}
    if tiles:
        scene['map']['default_tile']={'terrain':'ground','buildableType':1,'passableMask':1}
    p['scenarioDraft']=scene
    return p
def create(**kw):return Engine.create(Compiler(providers=providers()).compile(package(**kw),packages=[COLD]),seed=6216,providers=providers())
def deploy(s,at=0):s.submit({'action':'deploy','definition':'unit/test/frstar2/player','alias':'player','position':{'row':2,'col':3}},at=at)
def kill(s,at):s.submit({'action':'skill','source':'controller','ability':'ability/test/frstar2/kill'},at=at)
def hp(s,who='boss'):return s.ctx.resources.current(who,'hp')
def flags(s,who):return s.ctx.spatial.selection_state(who,DEFAULT_STATE)['abnormal_flags']
def events(s,name):return [e for e in s.session.events if e['type']==name]
def dealt(s):return [(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted') if e['payload']['source']==s.session.world.resolve('boss')]

def test_exact_profile_and_true_intrinsic_immunity_source():
    p=json.loads((OUT/'model.json').read_bytes());u=p['entities'][0];a=u['components']['attributes']['base']
    assert (a['max_hp'],a['atk'],a['def'],a['mres'],a['mass_level'],a['attack_interval'])==(30000,440,380,50,6,3.7)
    assert u['components']['selection_state']['abnormal_immunes']==[0,12,16,25]
    assert u['components']['rebirth']['delay_seconds']==10 and u['components']['rebirth']['restore_ratio']==1

def test_real_ground_normal28_flight_cold5_and_no_duplicate_mode_payload():
    s=create();deploy(s);s.session.advance(32)
    assert dealt(s)==[(31,330)]
    assert len(events(s,'projectile.launched'))==1 and 23 in flags(s,'player')
    buff=next(b for b in s.ctx.get('player',('buffs','instances'),[]) if b['definition']=='buff/ch6/cold/e2c_cold')
    assert buff['expires_at']==181

def test_real_zero_hp_ten_second_rebirth_full_restore_atk_and_twenty_invul():
    s=create();deploy(s);kill(s,at=5);s.session.advance(6)
    assert hp(s)==0 and s.ctx.alive('boss') and not s.ctx.active('boss')
    assert len(events(s,'entity.rebirth.started'))==1 and not events(s,'entity.died')
    s.session.advance(299);assert hp(s)==0
    s.session.advance(1);assert hp(s)==30000 and s.ctx.active('boss') and s.ctx.attributes.value('boss','atk')==660
    assert 5 in flags(s,'boss')
    kill(s,at=307);s.session.advance(3);assert hp(s)==30000
    s.session.advance(596);assert 5 not in flags(s,'boss')
    kill(s,at=906);s.session.advance(2)
    assert hp(s)==0 and not s.ctx.alive('boss') and len(events(s,'entity.died'))==1

def test_burst_initial_cd_priority_area_damage_and_cold10_owned_multiplier():
    s=create();deploy(s);s.session.advance(364)
    starts=[(e['time'],e['payload']['ability']) for e in events(s,'ability.started') if e['payload']['source']==s.session.world.resolve('boss')]
    assert (315,B[0]) in starts and not any(t<315 and a in B for t,a in starts)
    assert (343,660) in dealt(s)
    assert any(e['payload']['priority']==1 for e in events(s,'ability.arbitrated') if e['payload']['ability']==B[0])

def test_phase1_burst_uses_skill3_87frame_range_and_atk660_not_old_frost():
    s=create();deploy(s);kill(s,5);s.session.advance(710)
    starts=[e for e in events(s,'ability.started') if e['payload']['ability']==B[1]]
    assert starts
    first=starts[0]['time'];assert any(t==first+87 for t,_ in dealt(s))
    assert not [e for e in events(s,'ability.started') if e['time']>305 and e['payload']['ability']==B[0]]

@pytest.mark.parametrize('tick',[3,6,304,306])
def test_public_profile_rebirth_or_postrestore_disk_cp_and_from_head(tick,tmp_path):
    s=create();deploy(s);kill(s,5);s.session.advance(tick)
    p=tmp_path/'frstar2.json';pin=write_ordered(p,s.checkpoint());restored=Engine.restore(s.program,load_bound(p,pin),providers=providers())
    s.session.advance(720-tick);restored.session.advance(720-tick)
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
