"""Exact source story/NPC/exit adapter checks; compile/run belongs to stage join."""
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter06_review.stage_converter_v6 import compose
from tools.chapter06_review.story_keys_v5 import convert,digest


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    plan=ROOT/'packages/campaign/chapter06_plans/source.plan.json'
    native=json.loads(plan.read_bytes())['stages']['level_main_06-15']['native_document']
    key='level_main_06-15';definitions={r['inst']['characterKey']:'unit/ch6/npc/'+r['inst']['characterKey'] for r in native['predefines']['characterInsts']}
    profile={'schema':'ark-sim/story-predefined-key-profile/v1','policy':'unique_native_character_key_for_hidden_null_alias',
        'native_id':key,'native_document_digest':digest(native),'bindings':[{'bucket':'characterInsts','index':i,
         'activation_key':r['inst']['characterKey'],'definition':definitions[r['inst']['characterKey']]} for i,r in enumerate(native['predefines']['characterInsts'])]}
    predefined=convert(native,key,definitions,story_key_profile=profile)
    stories_path=ROOT/'packages/campaign/chapter06_npcs/story_controls.v2.model.json'
    stories={c['metadata']['native_story_key']:c for c in json.loads(stories_path.read_bytes())['controls']}
    exitpath=ROOT/'packages/campaign/chapter06_exit_accounting/reference_policy.json'
    exitprofile=json.loads(exitpath.read_bytes())['actionLifecycleProfile']
    binding={'enemy_1510_frstar2_s':{'unit':'unit/explicit_pending/frstar2_s','motion':'WALK'}}
    def run(n=native,ps=None,story_profile=profile,pre=predefined):
        return compose(n,key,binding,{},story_controls=stories,predefined_profile=pre,story_key_profile=story_profile,
            action_lifecycle_profiles=[exitprofile] if ps is None else ps)
    scene,controls=run();actions=[a for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions']]
    spawn=next(a for a in actions if a['kind']=='spawn')
    assert spawn['metadata']['native_action']==exitprofile['native_action']
    assert spawn['spawn']['components']['lifecycle']==exitprofile['lifecycle']
    activations=[a for a in actions if a['kind']=='effects'];assert len(activations)==3
    native_activation_keys=[a['key'] for w in native['waves'] for f in w['fragments'] for a in f['actions'] if a['actionType']=='ACTIVATE_PREDEFINED']
    assert [a['effects'][0]['parameters']['key'] for a in activations]==native_activation_keys
    assert all(a['metadata']['native_action']['managedByScheduler'] and not a['managed'] for a in activations)
    assert scene['parameters']['deploy_capacity']==0 and scene['resources']['dp']['initial']==0 and scene['resources']['life']['initial']==1
    assert scene['seed']==native['randomSeed'] and len(controls)==5
    cases=[{'case':'native full source controls and one explicit exceptional birth converted','passed':True}]
    trials=[('missing_profile',lambda:run(ps=[])),('duplicate_profile',lambda:run(ps=[exitprofile,exitprofile]))]
    changed=deepcopy(exitprofile);changed['native_action']['routeIndex']=999;trials.append(('source_action_mismatch',lambda:run(ps=[changed])))
    wrong=deepcopy(predefined);wrong['initial_entities'][0]['registration_key']='fake';trials.append(('wrong_registered_key',lambda:run(pre=wrong)))
    for field,value in [('unharmful',1),('always_count_as_killed',1),('loss',True)]:
        bad=deepcopy(exitprofile);bad['lifecycle']['exit_parameters'][field]=value
        trials.append(('strict_lifecycle_'+field,lambda bad=bad:run(ps=[bad])))
    for name,fn in trials:
        try:fn()
        except ValueError:cases.append({'case':name,'rejected':True})
        else:raise AssertionError(name)
    out=ROOT/'validation/campaign/chapter06_converter_v6_sources_strict';out.mkdir(exist_ok=False)
    (out/'converted.json').write_text(json.dumps({'scene':scene,'controls':controls},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    report={'passed':True,'cases':cases,'source_pins':{str(p):sha(p) for p in [plan,stories_path,exitpath,Path(__file__),ROOT/'tools/chapter06_review/stage_converter_v6.py']},
        'scope':'Exact original source conversion and negative profiles. Deliberately pending boss definition; no compile/fullstage/actual native callback ordering claim'}
    p=out/'verification.json';p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'sha':sha(p)}))


if __name__=='__main__':main()
