"""Exact seven-phase branch of finite alias activations, rawsource preserved."""
import json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter08_source_prepare/integration/predefines.native.v2.json'
PROFILE=ROOT/'packages/campaign/chapter08_consumers/flame/predefines.profile.v2.json'
OUT=ROOT/'packages/campaign/chapter08_consumers/flame/branch.profile.v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    native=json.loads(SOURCE.read_bytes())['stages']['level_main_08-17']['native_branches']['bsnake_flame'];profile=json.loads(PROFILE.read_bytes());allowed={e['registration_key'] for e in profile['initial_entities']};phases=[]
    for i,phase in enumerate(native['phases']):
        actions=[]
        for raw in phase['actions']:
            assert raw['actionType']=='ACTIVATE_PREDEFINED' and raw['key'] in allowed
            assert raw['count']==1 and raw['preDelay']==raw['interval']==0 and raw['managedByScheduler'] is True
            assert raw['randomType']==raw['refreshType']=='ALWAYS' and raw['blockFragment'] is False and raw['forceBlockWaveInBranch'] is False
            actions.append({'pre_delay_seconds':raw['preDelay'],'count':raw['count'],'interval_seconds':raw['interval'],
                'effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':raw['key']}}]})
        phases.append({'pre_delay_seconds':phase['preDelay'],'actions':actions})
    assert len(phases)==7 and sum(len(p['actions']) for p in phases)==35
    return {'schema':'ark-sim/ch8-flame-branch-profile/v1','runtime_branch':{'bsnake_flame':{'phases':phases,'loop':False}},'native_branch':deepcopy(native),
        'source_locks':{str(x):sha(x) for x in (SOURCE,PROFILE,Path(__file__))},'reference_policy':'Exactsource7phases/35count1 activations; branchTrigger advancesnextphase after priorphasecomplete. Nonloop profile, native repeatedaliasusesfinitefreshincarnations. Hinttimer/selection/summonCD belongsBoss consumer, not fabricated here.'}
if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(sha(OUT))
