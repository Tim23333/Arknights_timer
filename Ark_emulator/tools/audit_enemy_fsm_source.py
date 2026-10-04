"""Offline exact mode/attack/FSM declaration audit, no runtime implementation."""
import argparse
import hashlib,json,re
from pathlib import Path
from copy import deepcopy
import UnityPy
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter01_sources/native.reference.json'
DUMP=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs'
OUTPUT=ROOT/'packages/campaign/chapter01_behavior/source.reference.json'
KEYS=('enemy_1014_rogue','enemy_1028_mocock','enemy_1028_mocock_2','enemy_1504_cqbw')
CLASSES=('Enemy.States.State','Enemy.States.Blackboard','Enemy.States.EnemyStateMachine','Enemy.States.MoveState','Enemy.States.AttackState',
 'Enemy.States.CombatState','Enemy.AttackWrapper','Enemy.CombatWrapper','Enemy','UnitMode','MoveController',
 'AbilityStandard.SelectTargetSource','AbilityStandard.SelectTargetTiming','Ability.FinishReason')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()=='a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd'
    j=json.loads(raw);cache={};locks={str(SOURCE):sha(SOURCE),str(DUMP):sha(DUMP)}
    def objects(src):
        p=ROOT.parent/src['path'];assert sha(p)==src['sha256'];locks[str(p)]=sha(p)
        if p not in cache:cache[p]={o.path_id:o for o in UnityPy.load(str(p)).objects}
        return cache[p]
    enemies={}
    for key in KEYS:
        n=j['enemies'][key];prefab=n['prefab'];o=objects(prefab['source']);parts={};links=[]
        for pid,c in prefab['components'].items():
            if c['native_class'] not in {'Enemy','UnitMode','MoveController','SelectorTrigger','RangedAttack','MultiMeleeAttack','AdvancedSelector','EnemyBlockerOrAdvancedSelector'}:continue
            actual=o[int(pid)].read_typetree();assert actual==c['raw']
            script=j['native_monoscripts'][c['script_key']];typetree=objects(script['source'])[script['path_id']].read_typetree()
            assert typetree==script['raw'] and typetree['m_ClassName']==c['native_class']
            parts[pid]={'native_class':c['native_class'],'raw':deepcopy(actual),'source':prefab['source'],'script':script}
            if c['native_class']=='UnitMode':
                pointers={p:actual[p] for p in ('_combat','_attack','_attackTrigger')}
                targets={p:prefab['components'].get(str(pointer['m_PathID']),{}).get('native_class') if pointer['m_PathID'] else None for p,pointer in pointers.items()}
                assert all(pointer['m_FileID']==0 for pointer in pointers.values())
                links.append({'mode_path_id':int(pid),'pointers':pointers,'resolved_classes':targets})
        enemies[key]={'native_DB':n['native_enemy'],'prefab_source':prefab['source'],'components':parts,'mode_links':links}
    text=DUMP.read_text(encoding='utf8');lines=text.splitlines();declarations={}
    for cls in CLASSES:
        pattern=re.compile(r'^(?:public|private|internal|protected)\s+(?:(?:abstract|sealed|static)\s+)*(?:class|enum)\s+'+re.escape(cls)+r'(?:\s|:)')
        start=next((i for i,l in enumerate(lines) if pattern.match(l)),None);assert start is not None,cls
        end=next((i for i in range(start+1,len(lines)) if lines[i].startswith('// Namespace:')),len(lines))
        block=lines[start:end]
        declarations[cls]={'start_line':start+1,'raw_declaration':'\n'.join(block),
          'method_signatures':[l.strip() for l in block if '(' in l and (l.strip().endswith('{ }') or l.strip().endswith(';'))],
          'native_method_bodies_present':False}
    assert 'public const AbilityStandard.SelectTargetSource INPUT_TARGET = 2;' in declarations['AbilityStandard.SelectTargetSource']['raw_declaration']
    rogue=enemies['enemy_1014_rogue']['mode_links'][0]
    assert rogue['resolved_classes']=={'_combat':'MultiMeleeAttack','_attack':None,'_attackTrigger':None}
    for key in ('enemy_1028_mocock','enemy_1028_mocock_2','enemy_1504_cqbw'):
        assert all(x['pointers']['_combat']==x['pointers']['_attack'] and x['resolved_classes']['_attack']=='RangedAttack' and x['resolved_classes']['_attackTrigger']=='SelectorTrigger' for x in enemies[key]['mode_links'])
    return {'schema':'ark-sim/enemy-fsm-source-audit/v1','source_locks':locks,'extractor_sha256':sha(Path(__file__)),
       'enemies':enemies,'dump_declarations':declarations,'model_claims':False,'runtime_modified':False,'formal_approval':False,
       'boundary':'Exact serialized components/mode PPtr/MonoScript and empty-body dump declarations; no native move/cast permission formula recovered'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args();j=build();raw=(json.dumps(j,ensure_ascii=False,indent=2)+'\n').encode()
    if args.check:assert OUTPUT.read_bytes()==raw
    else:OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_bytes(raw)
    print(json.dumps({'enemies':len(j['enemies']),'classes':len(j['dump_declarations']),'locks':len(j['source_locks']),'sha256':sha(OUTPUT)}))
