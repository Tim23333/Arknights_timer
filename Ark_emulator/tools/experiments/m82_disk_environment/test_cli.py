import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m82_disk_environment_candidate'
HELPER=ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py'
CORE='65134744f50a9a1641f339965a8f4925927e5de51aedff9a39eea0550e887522'


def test_actual_disk_cli_complete_reference_cp_replay_never_materializes_history(tmp_path):
    p={'manifest':{'id':'package/disk_test','requires':['preset/ark_standard'],'metadata':{}},
       'entities':[{'id':'unit/enemy','kind':'entity','tags':['enemy'],'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'move_speed':30}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':1}}}],
       'scenarioDraft':{'id':'scene/disk','ruleset':'ruleset/ark_standard','seed':123,'resources':{'life':{'initial':99999,'capacity':99999}},
        'objectives':{'type':'waves','life_resource':'life'},'map':{'rows':1,'cols':3},'metadata':{'runthrough_profile':{'base_life_resource':'life'}},
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':.3,'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':'unit/enemy','position':{'row':0,'col':0},
            'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':2},'checkpoints':[]}}}]}]}]}}}
    package=tmp_path/'input.json';package.write_text(json.dumps(p),encoding='utf8');commands=tmp_path/'commands.json';commands.write_text(json.dumps([{'at':150,'action':'withdraw','source':'missing'}]),encoding='utf8')
    output=tmp_path/'report.json';helper_sha=hashlib.sha256(HELPER.read_bytes()).hexdigest()
    args=['tools/run_campaign_disk_runthrough_v15.py','--runtime-root',str(RUNTIME),'--expected-core',CORE,'--package',str(package),
        '--commands',str(commands),'--output',str(output),'--evidence-helper',str(HELPER),'--helper-sha256',helper_sha,'--checkpoint-at','4','--max-ticks','200']
    wrapper="""import sys,runpy
sys.path.insert(0,sys.argv[1])
from ark_sim.kernel.events import EventLog
def forbidden(self):raise AssertionError('Full history materialized')
EventLog.records=property(forbidden)
sys.argv=sys.argv[2:]
runpy.run_path(sys.argv[0],run_name='__main__')
"""
    process=subprocess.run([sys.executable,'-c',wrapper,str(RUNTIME),*args],cwd=ROOT,capture_output=True,text=True)
    assert process.returncode==0,process.stdout+process.stderr
    report=json.loads(output.read_bytes());assert report['passed'] and report['process_complete'] and report['checkpoint_equal'] and report['replay_equal']
    assert report['state']['leaks']==1 and report['base_life_final']==99998
    assert len(report['commands'])==1 and report['commands'][0]['time']==150 and report['commands'][0]['type']=='command.rejected'
    cp=json.loads(Path(report['checkpoint']).read_bytes());ref=cp['kernel']['events']['reference']
    assert ref==report['checkpoint_event_reference'] and hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest()==ref['sha256']
    for label in ('journal','continuation_journal','replayed_journal'):
        row=report[label];assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']
    bad=args[:];bad[bad.index('--helper-sha256')+1]='0'*64;bad[bad.index('--output')+1]=str(tmp_path/'bad.json')
    failed=subprocess.run([sys.executable,*bad],cwd=ROOT,capture_output=True,text=True);assert failed.returncode!=0 and 'Evidence helper bytes differ' in failed.stderr
