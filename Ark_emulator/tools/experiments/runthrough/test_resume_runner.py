"""Real saved-prefix resume through CLI, then full journal/CP/replay proof."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.campaign_ordered_checkpoint import write_ordered


def test_real_prefix_full_process_cli_and_mismatch_rejected(tmp_path):
    p={'manifest':{'requires':['preset/ark_standard'],'metadata':{'pending_model_gaps':[]}},
       'entities':[{'id':'unit/enemy','kind':'entity','tags':['enemy'],'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'move_speed':30}},
           'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':1}}}],
       'scenarioDraft':{'id':'scene/resume','ruleset':'ruleset/ark_standard','seed':123,'resources':{'life':{'initial':99999,'capacity':99999}},
          'objectives':{'type':'waves','life_resource':'life'},'map':{'rows':1,'cols':3},
          'metadata':{'runthrough_profile':{'base_life_resource':'life'}},
          'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':.3,'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':'unit/enemy','position':{'row':0,'col':0},
           'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':2},'checkpoints':[]}}}]}]}]}}}
    package=tmp_path/'input.json';package.write_text(json.dumps(p),encoding='utf8');commands=tmp_path/'commands.json';commands.write_text('[]',encoding='utf8')
    s=Engine.create(Compiler().compile(p),seed=123);s.advance(4);cp=tmp_path/'prefix.json';pin=write_ordered(cp,s.checkpoint());output=tmp_path/'report.json'
    args=[sys.executable,'tools/resume_campaign_runthrough_v1.py','--runtime-root',str(RUNTIME),'--expected-core',implementation_digest(),
       '--package',str(package),'--commands',str(commands),'--resume-checkpoint',str(cp),'--resume-sha256',pin,'--output',str(output),'--max-ticks','200']
    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads(output.read_bytes());assert report['passed'] and report['checkpoint_equal'] and report['replay_equal']
    assert report['state']['leaks']==1 and report['resumed_from']['prefix_tick']==4
    bad=args[:];bad[bad.index('--resume-sha256')+1]='0'*64;bad[bad.index('--output')+1]=str(tmp_path/'bad.json')
    failed=subprocess.run(bad,cwd=ROOT,capture_output=True,text=True);assert failed.returncode!=0 and 'Durable checkpoint bytes changed' in failed.stderr
