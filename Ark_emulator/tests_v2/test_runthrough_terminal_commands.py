import json
from pathlib import Path
import subprocess
import sys
import pytest

from ark_sim.adapters.api import implementation_digest
from tools.build_campaign_runthrough_input import apply,encoded

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('runner',['run_campaign_streaming_runthrough_v7.py','run_campaign_streaming_runthrough_v8.py','run_campaign_streaming_runthrough_v9.py','run_campaign_streaming_runthrough_v10.py'])
def test_complete_battle_keeps_post_terminal_command_outcomes_and_durable_replay(tmp_path,runner):
    import ark_sim
    runtime=Path(ark_sim.__file__).resolve().parents[1]
    source={'manifest':{'id':'package/test/early_finish','metadata':{}},'entities':[{
        'id':'unit/test_walker','kind':'entity','tags':['enemy','ground'],'components':{
            'attributes':{'base':{'max_hp':10,'move_speed':30}},'resources':{'hp':{'initial':10,'capacity':10,'role':'health'}},
            'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],
        'scenarioDraft':{'id':'scene/test/early_finish','ruleset':'ruleset/ark_standard','seed':7,
            'metadata':{},'resources':{'life':{'initial':3,'capacity':3}},'objectives':{'type':'waves','life_resource':'life'},
            'map':{'rows':1,'cols':2},'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear',
                'waves':[{'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':'unit/test_walker','instanceAlias':'walker',
                    'position':{'row':0,'col':0},'route':{'motionMode':'WALK','endPosition':{'row':0,'col':1},'checkpoints':[]}},
                    'managed':True,'blocks_wave':True}]}]}]}}}
    package=tmp_path/'package.json';package.write_bytes(encoded(apply(source,'test_synthetic_parent')))
    commands=tmp_path/'commands.json';commands.write_text(json.dumps([{'at':150,'action':'withdraw','source':'walker'}]),encoding='utf8')
    out=tmp_path/'result.json'
    result=subprocess.run([sys.executable,str(ROOT/'tools'/runner),
        '--runtime-root',str(runtime),'--expected-core',implementation_digest(),'--package',str(package),'--commands',str(commands),
        '--output',str(out),'--max-ticks','300','--checkpoint-at','1'],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads(out.read_bytes())
    assert report['passed'] and report['process_complete'] and report['identity_stable']
    assert report['terminal_tick']<150 and report['end_tick']>150
    assert report['state']['leaks']==1 and report['base_life_final']==99998
    assert len(report['commands'])==1
    assert report['commands'][0]['type']=='command.rejected'
    assert report['commands'][0]['payload']['reason']=='scenario already finished'
    assert report['checkpoint_equal'] and report['durable_checkpoint_equal'] and report['replay_equal']
