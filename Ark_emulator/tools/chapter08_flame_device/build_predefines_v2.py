"""Exact ten native hiddendevices and finite branchactivation incarnation budgets."""
import json,hashlib
from pathlib import Path
from collections import Counter
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter08_source_prepare/integration/predefines.native.v2.json'
OUT=ROOT/'packages/campaign/chapter08_consumers/flame/predefines.profile.v2.json'
UNIT='unit/ch8/flame/level1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert sha(SOURCE)=='f112ab9ad06f19bd050a997d5fe0d9d10b6c18afce3355143a2d28951e49e282'
    plan=ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json'
    raw=json.loads(plan.read_bytes())['stages']['level_main_08-17']['native_document']
    s=json.loads(SOURCE.read_bytes())['stages']['level_main_08-17'];native=s['native_predefines'];rows=len(raw['mapData']['map'])
    assert rows==9 and raw['predefines']==native
    # All budgets derive only from the frozen nativebranch action graph; hint
    # selects phase order but never manufactures a new nativeactivation alias.
    counts=Counter(a['key'] for f in s['native_branches']['bsnake_flame']['phases'] for a in f['actions'] if a['actionType']=='ACTIVATE_PREDEFINED')
    entities=[]
    for raw in native['tokenInsts']:
        assert raw['inst']=={'characterKey':'trap_021_flame','level':1,'phase':'PHASE_0','favorPoint':0,'potentialRank':0}
        assert raw['hidden'] is True and raw['skillIndex']==0 and raw['mainSkillLvl']==1 and not raw['overrideSkillBlackboard'] and not raw['overrideTalents'] and not raw['uniEquipIds']
        assert raw['alias'] in counts
        entities.append({'definition':UNIT,'position':{'row':rows-1-raw['position']['row'],'col':raw['position']['col']},'facing':raw['direction'].lower(),
            'active':False,'registration_key':raw['alias'],'reactivation':{'max_activations':counts[raw['alias']],'after_reasons':['withdrawn','dead']},
            'parameters':{'native_bucket':'tokenInsts','native_instance':deepcopy(raw)}})
    assert len(entities)==10 and sum(counts.values())==35
    return {'schema':'ark-sim/ch8-flame-predefine-profile/v1','native_predefines':deepcopy(native),'initial_entities':entities,'card_bindings':[],'resources':{},
        'native_branch':s['native_branches'],'source_locks':{str(SOURCE):sha(SOURCE),str(plan):sha(plan),str(Path(__file__)):sha(Path(__file__))},
        'reference_policy':'Sourcehidden registration noinstancealias; boundednative totalphaseactivations, freshincarnation afterwithdraw/dead preservesoldsourceprojectiles. Currentbranch7phases onceeach yields35activations, no unlimitedrespawn policy.'}
if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(sha(OUT))
