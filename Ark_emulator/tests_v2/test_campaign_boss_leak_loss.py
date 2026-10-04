from copy import deepcopy
import json
from pathlib import Path

from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay

ROOT=Path(__file__).resolve().parents[1]


def test_actual_skulsr_source_two_base_life_loss_is_one_enemy_lifecycle():
    p=json.loads((ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.reference_module.json').read_bytes())
    boss=next(d for d in p['definitions'] if d['kind']=='entity' and 'skulsr' in d['id'])
    assert boss['components']['lifecycle']['leak_loss']==2
    p['scenarioDraft']={'id':'scene/test/boss_leak','ruleset':'ruleset/ark_standard','objectives':{'type':'waves','life_resource':'life'},
        'resources':{'life':{'initial':99999,'capacity':99999}},'map':{'rows':1,'cols':1},
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[
            {'kind':'spawn','managed':True,'blocks_wave':True,'spawn':{'definition':boss['id'],'position':{'row':0,'col':0},
                'route':{'motionMode':'WALK','endPosition':{'row':0,'col':0},'checkpoints':[]}}}]}]}]}}
    s=Engine.create(Compiler().compile(p),seed=4991);s.advance(2)
    assert s.ctx.state()['leaks']==1 and s.ctx.state()['kills']==0
    assert s.ctx.resources.current('system/battle','life')==99997
    assert s.ctx.state()['finished'] and s.ctx.state()['pending_waves']==0
    from tools.campaign_life_ledger import ledger
    before=s.checkpoint();balance=ledger(s,'life')
    assert balance['total_calculated_leak_loss']==2 and balance['leaked_entity_count']==1
    assert balance['only_leak_loss_balance_equal'] and balance['calculation_exit_count_equal'] and s.checkpoint()==before
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
