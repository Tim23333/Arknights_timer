import json
from pathlib import Path

from ark_sim import Compiler,Engine
from tools.build_chapter02_09_stage_v3 import build

ROOT=Path(__file__).resolve().parents[3]


def test_complete_source_scheduling_map_states_and_five_enemy_closure():
    p=build();native=json.loads((ROOT/'packages/campaign/native_reference/level_main_02-09.json').read_bytes())
    scene=p['scenarioDraft'];program=Compiler().compile(p)
    assert len(scene['roster'])==12
    waves=scene['timeline']['waves'];assert len(waves)==len(native['waves'])
    for output,source in zip(waves,native['waves']):
        assert output['max_wait_seconds']==source['maxTimeWaitingForNextWave']
        for fragment,original in zip(output['fragments'],source['fragments']):
            assert len(fragment['actions'])==len(original['actions'])
            for action,raw in zip(fragment['actions'],original['actions']):
                assert action['count']==raw['count']
                assert action['delay_seconds']==raw['preDelay']
                assert action['managed']==raw['managedByScheduler']
                assert action['blocks_fragment']==raw['blockFragment']
                assert action['blocks_wave']==(not raw['dontBlockWave'])
    actions=[a for w in waves for f in w['fragments'] for a in f['actions']]
    assert sum(a['count'] for a in actions if a['kind']=='spawn')==52
    assert sum(a['count'] for a in actions if a['kind']=='control')==7
    assert sum(t['tileKey']=='tile_hole' for t in scene['map']['tiles'])==32
    for uid in ('unit/chapter02/enemy_1005_yokai','unit/chapter02/enemy_1005_yokai_2','unit/chapter02/enemy_1017_defdrn'):
        spatial=program.definitions[uid]['components']['spatial']
        assert spatial['motion_mode']==1
        assert spatial['steering']['parameters']['response_factor']==20
        assert spatial['steering']['parameters']['max_acceleration']==100
    assert 'unit/chapter01_w' not in program.definitions
    for definition in program.definitions.values():
        if definition['kind']=='entity' and 'enemy' in definition.get('tags',[]):
            assert definition['components']['selection_state']['motion'] in (1,2)
    assert all(a['spawn']['route']['checkpoints'] is not None for a in actions if a['kind']=='spawn')
    s=Engine.create(program,seed=scene['seed']);s.advance(30)
    assert set(s.ctx.state()['tile_fields'])=={'3:3','3:7'}
    assert not any('enemy' in e['tags'] for e in s.session.world.entities())
    assert s.ctx.resources.current('system/battle','life')==3


def test_actual_airdrop_and_drone_both_receive_field_attacks_without_missing_typed_state():
    from ark_sim.tools.replay import replay
    p=build();p['scenarioDraft'].pop('timeline');p['scenarioDraft']['objectives']={}
    defs={d['id']:d for d in p['definitions']}
    uid='unit/char_103_angel';unit=defs[uid]
    unit['components']['attributes']['base']['atk']=200
    unit['components']['buffs']={'initial':[]};unit['components'].pop('behavior',None)
    unit['components']['abilities']=['ability/test_stage_motion_packet']
    p['definitions']+= [{'id':'selector/test_stage_targets','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}]},
        {'id':'ability/test_stage_motion_packet','kind':'ability','selector':'selector/test_stage_targets','activation':{'mode':'manual',
         'on_start':[{'op':'damage','damage_type':'physical'}]},'timeline':[]}]
    # Actual native cell(3,3) field, real source units and their source state.
    p['scenarioDraft']['initialEntities']=[{'definition':uid,'instanceAlias':'angel','position':{'row':3,'col':3}},
        {'definition':'unit/chapter02/enemy_1005_yokai','instanceAlias':'drone','position':{'row':3,'col':4}},
        {'definition':'unit/chapter02/enemy_1013_airdrp/level_0/20e3225f73e1c6e6','instanceAlias':'airdrop','position':{'row':3,'col':2}}]
    s=Engine.create(Compiler().compile(p),seed=4909)
    s.submit({'action':'skill','source':'angel','ability':'ability/test_stage_motion_packet'},at=0);s.advance(1)
    hits={e['payload']['target']:e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted'}
    assert hits[s.session.world.resolve('drone')]==290
    assert hits[s.session.world.resolve('airdrop')]==100
    assert not any(e['type']=='command.rejected' for e in s.session.events)
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
