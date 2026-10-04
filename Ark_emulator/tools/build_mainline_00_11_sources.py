"""Offline 0-11 native attacks/controls. No M6/M7 artifact is modified."""
from __future__ import annotations
import argparse
import base64
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
LEVEL_ID='level_main_00-11'
OUT=ROOT/'packages/campaign'
ARTIFACTS={'source':OUT/'sources.00_11.reference.json','attacks':OUT/'enemies.00_11.attacks.json',
    'control':OUT/'controls.00_11.model.json'}
EVIDENCE=ROOT/'validation/campaign/source_00_11_assertions.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf8'))
def record(path):return {'path':path.relative_to(ROOT.parent).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size}


def story_source():
    path=ROOT.parent/'unpack_work/release_20260831/hot_raw/main_00-11.dat';raw=path.read_bytes()
    size=struct.unpack_from('<I',raw)[0]
    if raw[4:4+size]!=b'main_00-11':raise ValueError('Unexpected story TextAsset name')
    off=(4+size+3)//4*4;length=struct.unpack_from('<I',raw,off)[0]
    if off+4+length>len(raw) or any(raw[off+4+length:]):raise ValueError('Story length/trailing padding invalid')
    payload=raw[off+4:off+4+length];text=payload.decode('utf8');commands=[]
    for lineno,line in enumerate(text.splitlines(),1):
        m=re.fullmatch(r'\[(HEADER|PopupDialog|Blocker)\((.*)\)\]\s*(.*)',line)
        if m is None:raise ValueError(f'Unsupported native story/gameplay command at line{lineno}: {line}')
        commands.append({'line':lineno,'command':m[1],'native_parameters':m[2],'text':m[3],'raw_line':line})
    if [c['command'] for c in commands]!=['HEADER','PopupDialog','PopupDialog','Blocker']:
        raise ValueError('0-11 story command sequence changed')
    return {'source':record(path),'payload_offset':off+4,'payload_sha256':hashlib.sha256(payload).hexdigest(),
        'payload_base64':base64.b64encode(payload).decode(),'script':text,'commands':commands,
        'native_UI_callbacks_verified':False}


def animation_sources(prefabs):
    import UnityPy
    from tools.extract_campaign_animation_bindings import unity_payload,parse_spine
    cache={}
    art_paths=[p for p in (ROOT.parent/'data/refs/arts').glob('enm_art_*.ab_unpacked/CAB-*') if not p.name.endswith('.resS')]
    def load(path):
        if path not in cache:
            env=UnityPy.load(str(path));objects={o.path_id:o for o in env.objects}
            trees={o.path_id:o.read_typetree() for o in env.objects if o.type.name=='MonoBehaviour'}
            cache[path]=(objects,trees,next(iter(env.files.values())))
        return cache[path]
    def pointer(reference,path):
        if not reference.get('m_PathID'):raise ValueError('Required animation pointer null')
        if reference['m_FileID']:
            file=load(path)[2];index=reference['m_FileID']-1
            if not 0<=index<len(file.externals):raise ValueError('Animation external index invalid')
            name=file.externals[index].path.rsplit('/',1)[-1]
            paths=[p for p in art_paths if p.name==name]
            if len(paths)!=1:raise ValueError('Exact animation external CAB missing/ambiguous')
            path=paths[0]
        objects,trees,_=load(path)
        if reference['m_PathID'] not in objects:raise ValueError('Animation external path ID absent')
        return path,objects[reference['m_PathID']],trees.get(reference['m_PathID'])
    found={}
    for key,prefab in prefabs.items():
        path=ROOT.parent/prefab['source'];objects,trees,_=load(path)
        go=next(o for o in objects.values() if o.type.name=='GameObject' and o.read().m_Name==key)
        roots=[trees[c.component.path_id] for c in go.read().m_Component if c.component.path_id in trees and '_modes' in trees[c.component.path_id]]
        if len(roots)!=1:raise ValueError('Exact enemy root ambiguous')
        apath,aobj,animator=pointer(roots[0]['_animator'],path)
        if animator is None or '_animations' not in animator or '_skeleton' not in animator:
            raise ValueError('Exact single-skeleton enemy Animator missing')
        rpath,robj,renderer=pointer(animator['_skeleton'],apath)
        dpath,dobj,data=pointer(renderer['skeletonDataAsset'],rpath)
        tpath,tobj,_=pointer(data['skeletonJSON'],dpath)
        if tobj.type.name!='TextAsset':raise ValueError('Skeleton JSON pointer not TextAsset')
        wrapper=tobj.get_raw_data();length=struct.unpack_from('<I',wrapper)[0];name=wrapper[4:4+length].decode('utf8')
        if name!=key+'.skel':raise ValueError('Skeleton identity differs from selected exact prefab')
        payload=unity_payload(wrapper);parsed=parse_spine(payload)
        found[key]={'source':record(tpath),'textasset_path_id':tobj.path_id,'name':name,
            'wrapper_sha256':hashlib.sha256(wrapper).hexdigest(),'payload_sha256':hashlib.sha256(payload).hexdigest(),
            'payload_base64':base64.b64encode(payload).decode(),'parsed':parsed,
            'animator':{'path_id':aobj.path_id,'source':record(apath),'fields':{k:v for k,v in animator.items() if not k.startswith('m_')}},
            'renderer':{'path_id':robj.path_id,'source':record(rpath),'fields':{k:v for k,v in renderer.items() if not k.startswith('m_')}},
            'data_asset':{'path_id':dobj.path_id,'source':record(dpath),'fields':{k:v for k,v in data.items() if not k.startswith('m_')}},
            'native_root_fields':{k:v for k,v in roots[0].items() if not k.startswith('m_')},
            'root_mover_components':[{'path_id':pid,'script_path_id':t['m_Script']['m_PathID'],
                'fields':{k:v for k,v in t.items() if not k.startswith('m_')}} for pid,t in trees.items()
                if t.get('m_GameObject',{}).get('m_PathID')==go.path_id and '_steeringFactor' in t]}
    return found


def control_package(plan,native,story):
    scheduled=[];counts=Counter();cursor=0
    def emit(name,payload):return {'op':'emit','target':'battle','event':name,'payload':payload}
    for wi,wave in enumerate(plan['native_wave_script']):
        cursor+=wave['preDelay']
        for fi,fragment in enumerate(wave['fragments']):
            start=cursor+fragment['preDelay'];end=start
            for ai,action in enumerate(fragment['actions']):
                if action['blockFragment'] or action['actionType'] not in ('SPAWN','STORY','DISPLAY_ENEMY_INFO'):
                    raise ValueError('Unsupported native action/gating; no control may be dropped')
                if action['count']:end=max(end,start+action['preDelay']+(action['count']-1)*action['interval'])
                if action['actionType']=='SPAWN':continue
                counts[action['actionType']]+=action['count']
                for repeat in range(action['count']):
                    origin={'native_action':deepcopy(action),'native_wave':wi,'native_fragment':fi,'native_action_index':ai,'repeat':repeat}
                    if action['actionType']=='STORY':
                        if action['key']!='obt/tutorial/level/main_00-11':raise ValueError('Unsupported native story reference')
                        lock={'op':'input_lock','target':'battle','parameters':{'key':action['key'],'enabled':True}}
                        effect=emit('native.control',origin);effect['effects']=[lock,emit('story.started',origin)]
                        effect['effects'] += [emit('story.command',deepcopy(c)) for c in story['commands']]
                        effect['effects'] += [{**deepcopy(lock),'parameters':{'key':action['key'],'enabled':False}},
                            emit('story.finished',{'key':action['key'],'policy':'headless_ack_zero_game_time_v1'})]
                    else:
                        effect=emit('enemy.info_displayed',{**origin,'native_preview_route':
                            deepcopy(native['routes'][action['routeIndex']]) if action['autoPreviewRoute'] else None})
                    scheduled.append({'at_seconds':start+action['preDelay']+repeat*action['interval'],'effect':effect})
            cursor=end
        cursor+=wave['postDelay']
    if dict(counts)!=plan['control_counts']:raise ValueError('Native control count conservation failed')
    return {'schema':'ark-sim/native-control-model/v1','status':'explicit_headless_model',
        'source':story,'native_control_counts':dict(counts),'scheduledEffects':scheduled,
        'native_runes':deepcopy(native['runes']),'native_predefines':deepcopy(native['predefines']),
        'native_options':deepcopy(native['options']),'native_exclude_char_ids':deepcopy(native['excludeCharIdList']),
        'model_policy':{'id':'headless_ack_zero_game_time_v1','native_UI_wall_time_simulated':False},
        'client_validated':False,'formal_stage_approved':False,
        'pending':['native_UI_pause_input_and_callback_order','source_versions_alignment']}


def build():
    from tools.build_mainline_dependencies import build as dependency_plan
    from tools.build_campaign_enemy_attacks import recover
    from tools.extract_campaign_animation_bindings import resolve_animation,library_identity
    planpath=OUT/'mainline_dependencies'/f'{LEVEL_ID}.json';plan=read(planpath)
    if dependency_plan(LEVEL_ID)!=plan:raise ValueError('Frozen 0-11 dependency source changed')
    nativepath=OUT/'native_reference'/f'{LEVEL_ID}.json';native=read(nativepath)
    if plan['spawn_count']!=37 or plan['control_counts']!={'STORY':1,'DISPLAY_ENEMY_INFO':2}:raise ValueError('0-11 native counts changed')
    keys={r['native_id'] for r in plan['resolved_enemies']}
    if len(keys)!=6 or 'enemy_1007_slime_2' not in keys:raise ValueError('Exact six 0-11 enemy variants required')
    reader_before=library_identity()
    prefabs=recover(keys);animations=animation_sources(prefabs);abilities=[];selectors=[];enemies=[]
    if library_identity()!=reader_before:raise ValueError('Shared Spine reader/library mutated during offline extraction')
    for row in plan['resolved_enemies']:
        key=row['native_id'];p=prefabs[key];fields=p['combat_fields'];a=animations[key]
        if row['resolved']['prefabKey']!=key:raise ValueError('Enemy prefab key differs; explicit mapping required')
        if row['resolved']['applyWay']!='MELEE' or fields.get('_damageType') not in (1,2,3):raise ValueError('Unsupported enemy attack type')
        if fields.get('_projectileKey') or fields.get('_activeBuffs'):raise ValueError('Native projectile/on-hit dependency unresolved')
        if fields['_waitForAttackEvent']!=1:raise ValueError('Native attack needs different trigger conversion')
        bound=resolve_animation(fields['_animKey'],a['animator']['fields']['_animations'],a['parsed'])
        hits=[e for e in bound['events'] if e['name']=='OnAttack']
        if not hits:raise ValueError(f'{key}: source OnAttack absent; no timing fallback')
        sid=f'selector/{key}/blocked_target'
        selectors.append({'id':sid,'kind':'selector','region':{'type':'all','blocked_only':True},
            'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
        abilities.append({'id':f'ability/{key}/normal_attack','kind':'ability','activation':{'mode':'automatic_attack'},
            'selector':sid,'timeline':[{'at_seconds':e['seconds'],'effect':{'op':'damage',
                'scale':fields['_atkScale'],'damage_type':{1:'physical',2:'arts',3:'true'}[fields['_damageType']]}} for e in hits],
            'metadata':{'native_id':key,'source_combat_path_id':p['combat_path_id'],'exact_animation_binding':bound,
                'timing_policy':'unscaled_source_event_model','client_fsm_timing_verified':False}})
        enemies.append({'native_id':key,'resolved_native':row,'prefab':p,'animation':a,'exact_attack_binding':bound})
    story=story_source();control=control_package(plan,native,story)
    sources={'schema':'ark-sim/mainline-native-sources/v1','status':'native_fields_frozen_models_partial',
        'native_level_id':LEVEL_ID,'native_level':record(nativepath),'dependency_plan':record(planpath),
        'native_level_document':deepcopy(native),
        'spine_reader_identity':reader_before,'shared_reader_unchanged':True,
        'spawn_count':37,'spawn_counts_by_key':plan['spawn_counts_by_key'],'enemies':enemies,'story':story,
        'native_wave_script':deepcopy(native['waves']),'native_map_data':deepcopy(native['mapData']),
        'native_routes':deepcopy(native['routes']),'native_runes':deepcopy(native['runes']),
        'native_options':deepcopy(native['options']),'native_predefines':deepcopy(native['predefines']),
        'native_hard_predefines':deepcopy(native['hardPredefines']),'native_exclude_char_ids':deepcopy(native['excludeCharIdList']),
        'native_random_seed':native['randomSeed'],'native_branches':deepcopy(native['branches']),
        'client_validated':False,'formal_stage_approved':False,
        'helpers':{p:sha(ROOT/'tools'/p) for p in ('build_campaign_enemy_attacks.py','build_mainline_dependencies.py','extract_campaign_animation_bindings.py')},
        'builder_sha256':sha(Path(__file__))}
    attacks={'schemaVersion':2,'status':'source_backed_attack_models_partial','manifest':{
        'id':'package/campaign/enemy_attacks/00_11','version':'0.1.0','requires':['preset/ark_standard'],
        'metadata':{'native_level_id':LEVEL_ID,'source_package':'packages/campaign/sources.00_11.reference.json',
            'formal_stage_approved':False,'client_validated':False,
            'pending':['source_version_alignment','native_animation_scaling_and_attack_callback_timing']}},
        'abilities':abilities,'selectors':selectors}
    return {'source':sources,'attacks':attacks,'control':control}


def assertions_and_compile(values):
    from ark_sim import Compiler,Engine
    source=values['source'];attack=values['attacks'];control=values['control']
    assert len(attack['abilities'])==len(attack['selectors'])==len(source['enemies'])==6
    assert sum(source['spawn_counts_by_key'].values())==37
    assert len(control['scheduledEffects'])==3
    assert Counter(c['command'] for c in source['story']['commands'])==Counter({'HEADER':1,'PopupDialog':2,'Blocker':1})
    # Explicit toy scene validates reference closure/real controls, not native
    # unit stats or full-stage victory. It is never saved as official content.
    data=deepcopy(attack);data['entities']=[{'id':'unit/review_'+str(i),'kind':'entity','tags':['enemy'],
        'components':{'attributes':{'base':{'max_hp':1000,'atk':100,'def':0,'mres':0,'attack_interval':100,
            'attack_speed_ratio':1}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},
            'spatial':{},'abilities':[a['id']]}} for i,a in enumerate(attack['abilities'])]
    data['scenarioDraft']={'id':'scenario/00_11_source_compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},
        'roster':[e['id'] for e in data['entities']],'initialEntities':[],'scheduledEffects':deepcopy(control['scheduledEffects'])}
    program=Compiler().compile(data);sim=Engine.create(program);sim.advance(1)
    assert len([e for e in sim.session.events if e['type']=='story.command'])==4
    assert not sim.ctx.state().get('input_locks',[])
    last=max(e['at_seconds'] for e in control['scheduledEffects'])
    sim.advance(sim.ctx.quantize(last)+1-sim.session.time)
    displays=[e for e in sim.session.events if e['type']=='enemy.info_displayed']
    assert len(displays)==2 and [e['time'] for e in displays]==[1380,1410]
    assert [e['payload']['repeat'] for e in displays]==[0,1]
    frames={e['native_id']:[h['frame'] for h in e['exact_attack_binding']['events'] if h['name']=='OnAttack'] for e in source['enemies']}
    return {'schema':'ark-sim/offline-source-assertions/v1','native_level_id':LEVEL_ID,
        'source_assertions_passed':True,'exact_prefab_count':6,'native_spawn_count':37,
        'native_controls':control['native_control_counts'],'native_story_command_count':4,
        'attack_frames':frames,'toy_compiler_valid':True,'definitions':len(program.definitions),'rules':len(program.rules),
        'toy_headless_story_tick_zero_verified':True,'toy_enemy_info_ticks':[e['time'] for e in displays],
        'source_assertion_identities':{'builder_sha256':sha(Path(__file__)),'native_level_sha256':source['native_level']['sha256'],
            'dependency_plan_sha256':source['dependency_plan']['sha256'],'story_payload_sha256':source['story']['payload_sha256'],
            'artifact_sha256':{key:hashlib.sha256((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8')).hexdigest()
                for key,value in values.items()}},
        'full_native_stage_executed':False,'formal_stage_approved':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    values=build();evidence=assertions_and_compile(values)
    if args.check:
        for key,path in ARTIFACTS.items():
            if not path.exists() or read(path)!=values[key]:raise SystemExit(f'0-11 source/model changed: {path}')
        if not EVIDENCE.exists() or read(EVIDENCE)!=evidence:raise SystemExit('0-11 independent source assertions changed')
    else:
        for key,path in ARTIFACTS.items():path.write_text(json.dumps(values[key],ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        EVIDENCE.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(evidence,ensure_ascii=False))
