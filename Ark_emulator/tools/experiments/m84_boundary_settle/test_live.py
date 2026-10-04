from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def fixture():
    p={'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/target','kind':'entity','tags':['enemy'],'components':{
        'selection_state':{'side':1,'abnormal_immunes':[0,12,16,25]},'spatial':{},'attributes':{'base':{'max_hp':1000,'atk':20}},
        'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],
        'buffs':[{'id':'buff/immune_combo','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_combo_immunes':[0]}},
          {'id':'buff/sleep','kind':'buff','control_rule':'rule/sleep','selection_flags':{'abnormal_combos':[0]},'control':{'move':False,'attack':False},'modifiers':[{'attribute':'atk','layer':'flat','value':7}]},
          {'id':'buff/mixed','kind':'buff','active_rule':'rule/active','selection_flags':{'abnormal_flags':[9],'abnormal_immunes':[0]},'modifiers':[{'attribute':'atk','layer':'flat','value':13}]},
          {'id':'buff/silence','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_flags':[12]}}],
        'rules':[{'id':'rule/sleep','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'0 in inputs.status.abnormal_combos'}},
          {'id':'rule/active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'12 not in inputs.status.abnormal_flags'}}],
        'scenarioDraft':{'id':'scene/rootimmune','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/target','instanceAlias':'t','position':{'row':0,'col':0}}],
           'dependencies':['buff/immune_combo','buff/sleep','buff/mixed','buff/silence']}}
    # Explicit reachable references belong on definitions, not guessed scans.
    p['entities'][0]['dependencies']=p['scenarioDraft'].pop('dependencies');return p


def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=70123)


def test_intrinsic_four_flags_do_not_accidentally_grant_sleep_combo_and_expiry_reactivates(tmp_path):
    s=make();s.ctx.buffs.apply('t','t','buff/immune_combo');s.ctx.buffs.apply('t','t','buff/sleep')
    assert s.ctx.buffs.controls('t')['attack'] and s.ctx.attributes.value('t','atk')==27
    assert s.ctx.spatial.selection_state('t',DEFAULT_STATE)['abnormal_combos']==[]
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.session.advance(3);r.session.advance(3)
    assert not s.ctx.buffs.controls('t')['attack']
    assert s.ctx.spatial.selection_state('t',DEFAULT_STATE)['abnormal_combos']==[0]
    assert s.checkpoint()==r.checkpoint()


def test_inactive_mixed_immunity_never_remains_live_contribution():
    p=fixture();p['entities'][0]['components']['selection_state']['abnormal_immunes']=[]
    s=make(p);s.ctx.buffs.apply('t','t','buff/mixed');s.ctx.buffs.apply('t','t','buff/silence')
    projected=s.ctx.spatial.selection_state('t',DEFAULT_STATE)
    assert projected['abnormal_flags']==[12] and projected['abnormal_immunes']==[] and s.ctx.attributes.value('t','atk')==20
    s.session.advance(3);projected=s.ctx.spatial.selection_state('t',DEFAULT_STATE)
    assert projected['abnormal_flags']==[9] and projected['abnormal_immunes']==[0] and s.ctx.attributes.value('t','atk')==33


def test_read_only_status_control_queries_no_event_or_random_consumption():
    s=make();s.ctx.buffs.apply('t','t','buff/immune_combo');s.ctx.buffs.apply('t','t','buff/sleep');before=s.checkpoint()
    for _ in range(20):s.ctx.spatial.selection_state('t',DEFAULT_STATE);s.ctx.buffs.controls('t')
    assert s.checkpoint()==before
