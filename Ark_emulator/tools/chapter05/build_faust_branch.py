"""Lossless supported faust_ballis phase conversion, without actor stubs."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter05_plans/source.plan.json'
PIN='c33c5a199fce73ef7b7524e0d29e59eeca6eb69a7f2ebd7d8c253634b050bee6'
def build():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==PIN
    source=json.loads(SOURCE.read_bytes());native=source['stages']['level_main_05-10']['native_document']['branches']['faust_ballis']
    assert set(native)=={'phases'} and len(native['phases'])==7
    phases=[];keys=[]
    for phase in native['phases']:
        assert set(phase)=={'preDelay','actions'}
        actions=[]
        for action in phase['actions']:
            assert action['actionType']=='ACTIVATE_PREDEFINED' and action['count']==1 and action['interval']==0
            assert action['managedByScheduler'] is True and action['randomType']==action['refreshType']=='ALWAYS'
            assert action['hiddenGroup'] is None and action['randomSpawnGroupKey'] is None and action['randomSpawnGroupPackKey'] is None
            assert not any(action[k] for k in ('blockFragment','autoPreviewRoute','autoDisplayEnemyInfo','isUnharmfulAndAlwaysCountAsKilled','dontBlockWave','forceBlockWaveInBranch'))
            assert action['routeIndex']==0 and action['weight']==0
            keys.append(action['key'])
            actions.append({'delay_seconds':action['preDelay'],'effects':[{'op':'activate_predefined','target':'battle',
                'parameters':{'key':action['key']}}]})
        phases.append({'pre_delay_seconds':phase['preDelay'],'actions':actions})
    assert keys==['trap_007_ballis#'+str(i) for i in range(1,11)]
    return {'schema':'ark-sim/chapter05/faust-branch-reference/v1',
        'source_locks':{str(SOURCE.relative_to(ROOT)):PIN},'native_branch':native,
        'branch_id':'faust_ballis','program':{'loop':False,'phases':phases},'required_registrations':keys,
        'policies':{'phase_progress':'Each accepted MoveNext advances one phase; next request only after previous delayed actions complete',
            'managed_native_flag':'Activation is existing registered actor, no new source birth; main wave membership handled separately',
            'source_retire':'Accepted phase tasks retain source attribution and complete unless battle terminal',
            'native_body_verified':False},'runtime_created':False,'full_stage_executed':False,'client_verified':False}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    p=ROOT/'packages/campaign/chapter05_boss/faust/branch.reference.json';raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:assert p.read_bytes()==raw
    else:
        p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    print(json.dumps({'path':str(p),'sha':hashlib.sha256(raw).hexdigest(),'phases':7,'activations':10,'checked':args.check}))
if __name__=='__main__':main()
