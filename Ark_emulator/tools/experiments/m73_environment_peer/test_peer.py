"""Fresh peer cases; no author test fixture or frozen-core edits."""
from pathlib import Path
from copy import deepcopy
import json,sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m73_environment_integrated_v2_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def scene(two=False,callback=None):
    effect={'op':'no_source_damage','fixed_amount':700.0,'damage_type':'true','attack_type':'NONE',
        'damage_without_modify':False,'ignore_for_sp':False,'node_is_env_damage':False,
        'env_blackboard_injected':True,'environmental':True,'origin':{'kind':'CastTile','condition':'raw origin [',
            'provider':'opaque source provider','rule':'opaque origin rule'},'rules':{'damage.pipeline':'rule/peer_fixed'}}
    profile={'type':'periodic_effect_field','origin':{'rule':'raw field rule','provider':'raw field provider','condition':'raw field ['},
        'expected_blackboard':{'damage':700.0,'low':.5,'high':.5},'effects':[effect],
        'trigger':{'rule':'rule/peer_clock','stream':'peer_field','sample_count':1,'parameters':{},'initial':{'mode':'fixed','seconds':.1}},
        'membership':{'rule':'rule/peer_members','parameters':{}}}
    rules=[{'id':'rule/peer_clock','kind':'rule','contract':'field.trigger','implementation':{'type':'provider','provider':'model.field.uniform_trigger'},
            'parameters':{'minimum_key':'low','maximum_key':'high'}},
        {'id':'rule/peer_members','kind':'rule','contract':'field.members','implementation':{'type':'provider','provider':'model.field.cell_combat_members'},
            'parameters':{'side_mask':3,'motion_mask':1,'category_mask':1,'extra_offsets':[[0,1]],
                'combat_policy':'blocked_or_attacking','exclude_flags':[9,17],'respect_target_free':True}},
        {'id':'rule/peer_fixed','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph',
            'nodes':[{'id':'settle','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}], 'output':'nodes.settle'}}]
    def unit(name,side):
        return {'id':'unit/'+name,'kind':'entity','tags':['player' if side==0 else 'enemy'],
            'components':{'selection_state':{'side':side,'motion':1,'category':1},'spatial':{},
                'attributes':{'base':{'max_hp':2000,'atk':0,'def':99999,'mres':99}},
                'resources':{'hp':{'initial':2000,'capacity':2000,'role':'health'}},'abilities':[],
                'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    entities=[unit('first',0),unit('second',1)]
    initial=[{'definition':e['id'],'instanceAlias':name,'position':{'row':0,'col':0}}
        for e,name in zip(entities,['first','second'])]
    p={'manifest':{'requires':['preset/ark_standard']},'rules':rules,'entities':entities,
        'scenarioDraft':{'id':'scene/peer_fields','ruleset':'ruleset/ark_standard','objectives':{},
            'initialEntities':initial,'map':{'rows':1,'cols':2,
                'tiles':[{'tileKey':'peer_field','passableMask':3,'buildableType':1,
                    'blackboard':{'damage':700.0,'low':.5,'high':.5}},
                    {'passableMask':3,'buildableType':1, **({'tileKey':'peer_field'} if two else {}),
                     **({'blackboard':{'damage':700.0,'low':.5,'high':.5}} if two else {})}],
                'tile_mechanics':{'peer_field':profile}}}}
    if callback:
        observer=unit('observer',0);observer['components']['abilities']=['ability/peer_callback'];entities.append(observer)
        initial.append({'definition':observer['id'],'instanceAlias':'observer','position':{'row':0,'col':1}})
        p['abilities']=[{'id':'ability/peer_callback','kind':'ability','activation':{'mode':'manual'},'timeline':[],
            'events':[{'event':'damage.accepted','condition':'inputs.payload.target == 2','effects':[callback]}]}]
    return p


def make(p=None):return Engine.create(Compiler().compile(p or scene()),seed=73191)
def events(s,kind):return [thaw(e) for e in s.session.events if e['type']==kind]


def test_two_fields_fixed_first_draw_order_actual_source_free_origin_reload(tmp_path):
    s=make(scene(two=True));s.session.advance(2)
    path=tmp_path/'cp.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin))
    s.session.advance(18);r.session.advance(18)
    fired=events(s,'field.triggered')
    assert [(e['time'],e['payload']['field_uid']) for e in fired]==[(3,'field/1'),(3,'field/2'),(18,'field/1'),(18,'field/2')]
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
    assert [sample['stream'] for sample in s.session.random.samples]==['peer_field']*4
    hits=events(s,'damage.accepted')
    assert all(e['payload']['source'] is None and e['payload']['node_is_env_damage'] is False
        and e['payload']['env_blackboard_injected'] is True and e['payload']['pipeline_amount']==700.0 for e in hits)
    assert hits[0]['payload']['origin']['condition']=='raw origin ['


@pytest.mark.parametrize('state',[{'abnormal_flags':[9]},{'abnormal_flags':[17]},{'target_free':True}, {'motion':2},{'category':4}])
def test_live_typed_membership_denies_unqualified_state(state):
    p=scene();p['entities'][0]['components']['selection_state'].update(state)
    s=make(p);s.session.advance(4)
    assert s.ctx.resources.current('first','hp')==2000
    assert s.ctx.resources.current('second','hp')==1300


def test_half_open_flag9_immunity_expiry_before_same_tick_pulse():
    p=scene();p['entities'][0]['components']['selection_state']['abnormal_flags']=[9]
    p['entities'][0]['components']['buffs']={'initial':['buff/peer_immunity']}
    p['buffs']=[{'id':'buff/peer_immunity','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_immunes':[9]}}]
    s=make(p);s.session.advance(4)
    assert s.ctx.resources.current('first','hp')==2000
    assert s.ctx.resources.current('second','hp')==1300


def test_target_after_hook_invulnerability_is_not_membership_or_source_damage_bypass():
    p=scene();p['entities'][0]['components']['buffs']={'initial':['buff/peer_invulnerable']}
    p['buffs']=[{'id':'buff/peer_invulnerable','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/peer_deny'}]}]
    p['rules'].append({'id':'rule/peer_deny','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph',
        'nodes':[{'id':'deny','expression':"{'accepted':False,'amount':0,'allocations':[],'events':[]}"}],'output':'nodes.deny'}})
    s=make(p);s.session.advance(4)
    assert s.ctx.resources.current('first','hp')==2000 and s.ctx.resources.current('second','hp')==1300
    assert len(events(s,'damage.rejected'))==1


@pytest.mark.parametrize('callback',[
    {'op':'retire','target':3,'parameters':{'reason':'withdrawn'}},
    {'op':'move','target':3,'position':{'row':0,'col':1}},
])
def test_legal_damage_subscription_mutates_second_before_remaining_packet(callback):
    s=make(scene(callback=callback));s.session.advance(4)
    # Required fresh-callback boundary: damage to first retires/moves second out
    # before a remaining packet is allowed to use its old selected membership.
    assert s.ctx.resources.current('second','hp')==2000
