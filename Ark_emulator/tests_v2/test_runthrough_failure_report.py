import json
from pathlib import Path
import subprocess
import sys
import pytest

from ark_sim.adapters.api import implementation_digest
from tools.build_campaign_runthrough_input import apply,encoded

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('runner',['run_campaign_streaming_runthrough_v9.py','run_campaign_streaming_runthrough_v10.py'])
def test_forward_rule_failure_preserves_actual_partial_journal_and_checkpoint(tmp_path,runner):
    import ark_sim
    runtime=Path(ark_sim.__file__).resolve().parents[1]
    p={'manifest':{'id':'package/test/actual_failure','metadata':{}},'entities':[{
        'id':'unit/test_failure','kind':'entity','tags':['enemy','ground'],'components':{'spatial':{},
            'attributes':{'base':{'max_hp':10,'move_speed':1}},'resources':{'hp':{'initial':10,'capacity':10}},
            'buffs':{'initial':['buff/test_periodic']}}}],
        'buffs':[{'id':'buff/test_periodic','kind':'buff','interval_seconds':.1,'effects':[
            {'op':'modify_resource','resource':'hp','amount_rule':'rule/test_fail'}]}],
        'rules':[{'id':'rule/test_fail','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1 / 0'}}],
        'scenarioDraft':{'id':'scene/test/forward_failure','ruleset':'ruleset/ark_standard','seed':9,'metadata':{},
            'resources':{'life':{'initial':3,'capacity':3}},'objectives':{'type':'waves','life_resource':'life'},
            'map':{'rows':1,'cols':3},'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[
                {'kind':'spawn','managed':True,'blocks_wave':True,'spawn':{'definition':'unit/test_failure','position':{'row':0,'col':0},
                    'route':{'motionMode':'WALK','endPosition':{'row':0,'col':2},'checkpoints':[]}}}]}]}]}}}
    package=tmp_path/'package.json';package.write_bytes(encoded(apply(p,'synthetic_failure')))
    commands=tmp_path/'commands.json';commands.write_text('[]',encoding='utf8');out=tmp_path/'report.json'
    r=subprocess.run([sys.executable,str(ROOT/'tools'/runner),'--runtime-root',str(runtime),
        '--expected-core',implementation_digest(),'--package',str(package),'--commands',str(commands),
        '--output',str(out),'--max-ticks','100','--checkpoint-at','1'],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==1,r.stdout+r.stderr
    d=json.loads(out.read_bytes())
    assert d['schema']=='ark-sim/campaign-runthrough-failure/v1' and d['phase']=='forward_execution'
    assert not d['passed'] and not d['process_complete'] and d['identity_stable']
    assert d['failed_tick']==3 and 'zero' in d['error']['message']
    assert d['journal']['events']==d['observations']['event_count']
    assert Path(d['failure_checkpoint']).exists() and d['failure_checkpoint_sha256']
    from tools.campaign_runthrough_progress import inspect
    status=inspect(tmp_path,{'package':package.name,'commands':commands.name,'report':out.name,'implementation':implementation_digest()})
    assert status['process_status']=='failed' and status['failed_tick']==3
    assert status['determinism_status']=='pending'
