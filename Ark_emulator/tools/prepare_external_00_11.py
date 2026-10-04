"""Independent external0-11 conversion draft; immutable battle bytes, no receipt."""
import argparse
import base64
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import build_first_model_conversion as common
read,sha,require,identity,record,leaves,lock,write=(getattr(common,k) for k in ('read','sha','require','identity','record','leaves','lock','write'))
CORE=common.CORE
SOURCE=ROOT/'packages/campaign/mainline_models/level_main_00-11.m12_projection.json'
PIN='0c8736089ebd08b1768499c4e043486275c2ccdbbb08f4fa6c4007590f55a149'
NATIVE=ROOT/'packages/campaign/native_reference/level_main_00-11.json'
NATIVE_PIN='f432d313e92466530cdf43d6b533c918b9237f9b0093a8b636511637f845975c'
COMMAND_SOURCE=ROOT/'validation/campaign/m12_primary_00_11_full_20261002.commands.json'
COMMAND_PIN='6947628516e57bfba40dd913559e01b43ba0b5d5d522e6fd95667928dbb47baf'
CONTENT=ROOT/'packages/mainline/v2/main_00-11.json'
COMMANDS=ROOT/'scenarios/mainline/v2/main_00-11/commands.json'
CONTRACT=ROOT/'packages/mainline/contracts/main_00-11.json'
AUDIT=ROOT/'packages/campaign/conversion_drafts/main_00-11.external.audit.json'


def native_audit(native,model):
    """Audit timeline groups and relative origins; never invent flat absolute times."""
    s=model['scenarioDraft'];rows=len(native['mapData']['map']);cols=len(native['mapData']['map'][0])
    require(s['map']['rows']==rows and s['map']['cols']==cols,'native map size mismatch')
    build={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3};passing={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3};tiles=[]
    for row in native['mapData']['map']:
        require(len(row)==cols,'nonrectangular matrix')
        for index in row:
            require(type(index) is int and 0<=index<len(native['mapData']['tiles']),'invalid palette index')
            t=native['mapData']['tiles'][index]
            require(set(t)=={'tileKey','heightType','buildableType','passableMask','playerSideMask','blackboard','effects'},'unknown palette field')
            require(t['playerSideMask']=='ALL' and not t['blackboard'] and not t['effects'],'active native tile addition requires converter')
            tiles.append({k:deepcopy(v) for k,v in dict(t,buildableType=build[t['buildableType']],passableMask=passing[t['passableMask']]).items() if k!='playerSideMask'})
    require(tiles==s['map']['tiles'],'palette/mask/topdown differs')
    options=native['options'];mapped={'characterLimit':s['parameters']['deploy_capacity'],'maxLifePoint':s['resources']['life']['initial'],
        'initialCost':s['resources']['dp']['initial'],'maxCost':s['resources']['dp']['capacity'],'costIncreaseTime':s['resources']['dp']['recovery']['interval_seconds']}
    for key,value in mapped.items():require(options[key]==value,'option not consumed: '+key)
    require(s['resources']['life']['capacity']==options['maxLifePoint'] and s['resources']['dp']['recovery_rate']==1/options['costIncreaseTime'],'resource capacity/rate differs')
    speed=next(r for r in model['rules'] if r['id']==s['rules']['movement.speed']);require(speed['parameters']['multiplier']==options['moveMultiplier'],'movement multiplier differs')
    inactive={'reachableCheckIgnoreStartTile':False,'isTrainingLevel':False,'isHardTrainingLevel':False,'isPredefinedCardsSelectable':False,
        'displayRestTime':False,'maxPlayTime':-1.0,'functionDisableMask':'NONE','configBlackBoard':None}
    require(set(options)==set(mapped)|{'moveMultiplier','steeringEnabled'}|set(inactive),'unknown option')
    require(options['steeringEnabled'] is True,'different steering policy')
    for k,v in inactive.items():require(options[k]==v,'active option requires converter: '+k)
    empty={'environmentSe','tilesDisallowToLocate','optionalRunes','globalBuffs','extraRoutes','enemies','branches','hardPredefines','excludeCharIdList','operaConfig','cameraPlugin'}
    for key in empty:require(not native[key],'active native root content: '+key)
    require(not any(native['predefines'].values()),'active predefines')
    require(all(not native['mapData'][k] for k in ('blockEdges','tags','effects','layerRects')),'active map extra')
    require(all(r['difficultyMask']=='FOUR_STAR' for r in native['runes']),'applicable rune')
    require(model['manifest']['metadata']['inactive_native_runes']==native['runes'],'inactive difficulty1 runes not preserved')
    tl=s['timeline'];require(tl['policy']=='managed_clear' and tl['negative_timeout_policy']=='wait_for_clear','timeline profile changed')
    require(len(tl['waves'])==len(native['waves'])==3,'native wave grouping changed')
    counts=Counter();origins=[];specials=[];controls=[];expanded_count=0;used=set()
    enemies={e['metadata']['native_id']:e for e in model['entities'] if 'enemy' in e.get('tags',[])}
    require(len(enemies)==6,'exact six enemies required')
    for wi,(nw,aw) in enumerate(zip(native['waves'],tl['waves'])):
        require(set(nw)=={'preDelay','postDelay','maxTimeWaitingForNextWave','fragments','advancedWaveTag'} and nw['advancedWaveTag'] is None,'unknown wave tag/field')
        require((aw['pre_delay_seconds'],aw['post_delay_seconds'],aw['max_wait_seconds'])==(nw['preDelay'],nw['postDelay'],nw['maxTimeWaitingForNextWave']),'wave pre/post/gate timeout mismatch')
        require(len(aw['fragments'])==len(nw['fragments']),'fragment grouping differs')
        for fi,(nf,af) in enumerate(zip(nw['fragments'],aw['fragments'])):
            require(set(nf)=={'preDelay','actions'} and af['pre_delay_seconds']==nf['preDelay'],'fragment delay/field differs')
            current=0
            for ai,na in enumerate(nf['actions']):
                defaults={'managedByScheduler':True,'blockFragment':False,'autoDisplayEnemyInfo':False,'isUnharmfulAndAlwaysCountAsKilled':False,
                    'hiddenGroup':None,'randomSpawnGroupKey':None,'randomSpawnGroupPackKey':None,'randomType':'ALWAYS','refreshType':'ALWAYS','weight':0,'dontBlockWave':False,'forceBlockWaveInBranch':False}
                require(set(na)==set(defaults)|{'actionType','key','count','preDelay','interval','routeIndex','autoPreviewRoute'},'unknown native action field')
                for k,v in defaults.items():require(na[k]==v,'active native action option needs converter: '+k)
                require(na['actionType'] in ('SPAWN','STORY','DISPLAY_ENEMY_INFO'),'unhandled native action')
                for repeat in range(na['count']):
                    actual=af['actions'][current];current+=1
                    require(actual['count']==1 and actual['delay_seconds']==na['preDelay']+repeat*na['interval'] and actual['interval_seconds']==na['interval'],'action repeat/relative clock mismatch')
                    origin={'wave':wi,'fragment':fi,'native_action':ai,'repeat':repeat,'delay_seconds':actual['delay_seconds'],
                        'frame_policy':'fragment_start after its preDelay; wave_start before preDelay; later waves wait managed clear'}
                    if na['actionType']=='SPAWN':
                        require(actual['kind']=='spawn','SPAWN replaced')
                        require((actual['managed'],actual['blocks_wave'],actual['blocks_fragment'])==(na['managedByScheduler'],not na['dontBlockWave'],na['blockFragment']),'SPAWN managed flags not consumed')
                        spawn=actual['spawn'];require(spawn['definition']=='unit/'+na['key'],'enemy replaced')
                        require(spawn['parameters']=={'native_wave':wi,'native_fragment':fi,'native_route_index':na['routeIndex'],'native_action':ai,'native_repeat':repeat},'source action origin/repeat linkage differs')
                        route=deepcopy(native['routes'][na['routeIndex']]);used.add(na['routeIndex'])
                        require(set(route)=={'motionMode','startPosition','endPosition','spawnRandomRange','spawnOffset','checkpoints','allowDiagonalMove','visitEveryTileCenter','visitEveryNodeCenter','visitEveryCheckPoint'},'unknown route field')
                        motion='FLY' if 'flying' in enemies[na['key']]['tags'] else 'WALK';require(route['motionMode'] in ('E_NUM',motion),'motion inference conflict');route['motionMode']=motion
                        for key in ('startPosition','endPosition'):route[key]['row']=rows-1-route[key]['row']
                        offset=False
                        for ci,cp in enumerate(route.get('checkpoints') or []):
                            require(set(cp)=={'type','time','position','reachOffset','randomizeReachOffset','reachDistance'},'unknown checkpoint field')
                            require(cp['type'] in ('MOVE','WAIT_CURRENT_FRAGMENT_TIME'),'unknown active checkpoint enum')
                            require(cp['randomizeReachOffset'] is False and cp['reachDistance']==0,'new checkpoint geometry semantics')
                            cp['position']['row']=rows-1-cp['position']['row']
                            if cp['type']=='WAIT_CURRENT_FRAGMENT_TIME':
                                require(cp['time']==30 and not any(cp['reachOffset'].values()),'fragment deadline source changed')
                                specials.append({**origin,'instance':spawn['instanceAlias'],'route_index':na['routeIndex'],'checkpoint':ci,
                                    'consumer':'runtime.spatial.timing_origins.fragment_start + quantize30s; WAIT position not a movement waypoint'})
                            offset=offset or any(cp['reachOffset'].values())
                        if offset:
                            route['reach_offset_policy']={'rule':'rule/m9_checkpoint_cartesian','parameters':{'axis_signs':{'row':-1,'col':1}}}
                            specials.append({**origin,'instance':spawn['instanceAlias'],'route_index':na['routeIndex'],'consumer':'MOVE(4,6)+row−.44/col+.44=(3.56,6.44)','nonzero_offset':True})
                        require(spawn['route']==route and spawn['position']==route['startPosition'],'route bottomup/deadline/offset policy mismatch')
                        place=spawn['placement'];require(place=={'rule':'rule/m7_spawn_rectangle','stream':'spawn','sample_axes':['col','row'],'sample_zero_range':False,
                            'random_range':{'row':route['spawnRandomRange']['y'],'col':route['spawnRandomRange']['x']},'offset':{'row':-route['spawnOffset']['y'],'col':route['spawnOffset']['x']}},'random spawn placement profile differs')
                        counts[spawn['definition']]+=1;expanded_count+=1
                    else:
                        require(actual['kind']=='effects' and actual['managed'] is False and actual['blocks_wave'] is False and actual['blocks_fragment'] is False,'headless synchronous control profile changed')
                        require(actual['metadata']=={'native_action':na,'completion_policy':'synchronous_headless_ack'},'control original flags/profile not retained')
                        effect=actual['effects'][0];payload=effect['payload']
                        require(payload['native_action']==na and payload['native_wave']==wi and payload['native_fragment']==fi and payload['native_action_index']==ai and payload['repeat']==repeat,'control source/repeat payload differs')
                        require(effect['event']==('native.control' if na['actionType']=='STORY' else 'enemy.info_displayed'),'control event substituted')
                        controls.append({**origin,'kind':na['actionType'],'native_managed':na['managedByScheduler'],'native_blocks_wave':not na['dontBlockWave'],
                            'model_completion':'synchronous effect retires at launch; no live control membership; semantic review required, not async native proof'})
                    origins.append(origin)
            require(current==len(af['actions']),'extra or missing converted actions')
    require(expanded_count==37 and len(origins)==40,'37SPAWN/3control conservation differs')
    require(Counter(x['kind'] for x in controls)=={'STORY':1,'DISPLAY_ENEMY_INFO':2},'native control population differs')
    require(len([s for s in specials if s.get('nonzero_offset')])==5 and len(specials)==7,'two deadlines/five offset copies missing')
    records=[]
    expected_roots={'options','levelId','mapId','bgmEvent','environmentSe','mapData','tilesDisallowToLocate','runes','optionalRunes','globalBuffs','routes','extraRoutes','enemies','enemyDbRefs','waves','branches','predefines','hardPredefines','excludeCharIdList','randomSeed','operaConfig','cameraPlugin'}
    require(set(native)==expected_roots,'unknown native root')
    for pointer,value in leaves(native):
        top=pointer.split('/')[1]
        if top in empty or top in ('predefines','runes'):kind='inactive_value';consumer='empty content/default guards or difficulty1 inactive FOUR_STAR runes'
        elif top in ('bgmEvent','levelId','mapId'):kind='presentation_only';consumer='retained source identification/audio'
        elif top=='randomSeed':kind='client_pending';consumer='scene.seed retains1995623974; stage CLI seed123 overrides; native RNG correspondence pending'
        elif top=='options':kind='inactive_value' if pointer.split('/')[2] in inactive else 'consumed_math';consumer='deploy8/life10/DP10-cap99-rate1/move*.5/steering'
        elif top=='routes':kind='consumed_math' if int(pointer.split('/')[2]) in used else 'inactive_value';consumer='timeline spawn.route/placement/current-fragment deadline and row−y col+x'
        elif top=='mapData':kind='inactive_value' if pointer.endswith('/playerSideMask') or any(pointer.startswith('/mapData/'+k) for k in ('blockEdges','tags','effects','layerRects')) else 'consumed_math';consumer='exact topdown matrix/palette/masks/height'
        elif top=='waves':
            kind='consumed_math';consumer='3waves/4fragments exact relative timeline; managed_clear/negative wait_for_clear'
            parts=pointer.split('/')
            if len(parts)>7 and parts[3]=='fragments' and parts[5]=='actions':
                action=native['waves'][int(parts[2])]['fragments'][int(parts[4])]['actions'][int(parts[6])]
                if action['actionType']!='SPAWN' and parts[7] in ('managedByScheduler','dontBlockWave','blockFragment'):
                    kind='gate_contract_gap';consumer='source flags retained; current explicit synchronous completion substitutes no live membership; independent control-flow semantic review required'
        else:kind='consumed_math';consumer='six pinnedDB/native prefab identities'
        records.append(record(NATIVE,pointer,value,kind,consumer,'known fields guarded and full converted structure asserted; unknown active contents reject; synchronous controls not presented as native async lifecycle'))
    return records,dict(counts),origins,specials,controls


def enemy_sources(model,native):
    source_path=ROOT/'packages/campaign/sources.00_11.reference.json';source=read(source_path)
    require(source['native_level_document']==native and source['native_level']['sha256']==sha(NATIVE),'enemy source level drift')
    require(model['manifest']['metadata']['m7_source_identities']['source_00_11']==sha(source_path),'model enemy/source reference mismatch')
    from tools.extract_campaign_animation_bindings import parse_spine,resolve_animation,library_identity
    reader_before=library_identity();rows=[];locks=[]
    for e in source['enemies']:
        cid=e['native_id'];asset=ROOT.parent/e['prefab']['source'];require(sha(asset)==e['prefab']['source_sha256'],'enemy prefab asset differs');locks.append(lock(asset))
        raw=e['prefab']['combat_fields'];animation=e['animation'];payload=base64.b64decode(animation['payload_base64'],validate=True)
        require(__import__('hashlib').sha256(payload).hexdigest()==animation['payload_sha256'],'frozenSpine payload identity differs')
        parsed=parse_spine(payload);require(parsed==animation['parsed'],'controlled privateBE Spine parse differs')
        bound=resolve_animation(raw['_animKey'],animation['animator']['fields']['_animations'],parsed);require(bound==e['exact_attack_binding'],'exactAnimator/Spine mapping differs')
        ability=next(a for a in model['abilities'] if a['id']==f'ability/{cid}/normal_attack')
        hits=[v for v in bound['events'] if v['name']=='OnAttack'];require(hits,'OnAttack source absent')
        require(ability['timeline']==[{'at_seconds':v['seconds'],'effect':{'op':'damage','scale':raw['_atkScale'],'damage_type':{1:'physical',2:'arts',3:'true'}[raw['_damageType']]}} for v in hits],'enemy attack frame/type/scale substitution')
        require(raw['_waitForAttackEvent']==1 and not raw.get('_activeBuffs') and not raw.get('_projectileKey'),'enemy combat dependencies not converted')
        for key in ('source','animator','renderer','data_asset'):
            rec=animation[key] if key=='source' else animation[key]['source'];p=ROOT.parent/rec['path'];require(sha(p)==rec['sha256'],'animation AB path/hash differs');locks.append(lock(p))
        entity=next(x for x in model['entities'] if x['id']=='unit/'+cid);movers=animation['root_mover_components'];require(len(movers)==1,'ambiguous mover')
        actual=entity['components']['spatial']['steering']['parameters'];fields=movers[0]['fields']
        require(actual=={'response_factor':fields['_steeringFactor'],'max_acceleration':fields['_maxSteeringForce'],'arrival_radius':.05},'mover constants not consumed')
        for pointer,value in leaves(raw):
            kind='consumed_math' if pointer in ('/_atkScale','/_damageType','/_animKey','/_waitForAttackEvent') else 'client_pending'
            r=record(asset,f'/combat/{e["prefab"]["combat_path_id"]}'+pointer,value,kind,ability['id'],'source exact frame/body fields; remaining native FSM/body decisions unverified');r['pointer_kind']='unity_object_pathid_and_typetree_field';rows.append(r)
    require(reader_before==library_identity()==source['spine_reader_identity'],'reader implementation/source identity drift')
    for name,digest in source['helpers'].items():require(sha(ROOT/'tools'/name)==digest,'source helper changed')
    story=source['story'];story_path=ROOT.parent/story['source']['path'];require(sha(story_path)==story['source']['sha256'],'story asset changed');locks.append(lock(story_path))
    require([c['command'] for c in story['commands']]==['HEADER','PopupDialog','PopupDialog','Blocker'],'story command shape changed')
    actual_story=model['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][0]['effects'][0]['effects']
    require([e['payload'] for e in actual_story if e.get('event')=='story.command']==story['commands'],'source story rows not consumed')
    return rows,locks


def build():
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    require(implementation_digest()==CORE and sha(SOURCE)==PIN and sha(NATIVE)==NATIVE_PIN and sha(COMMAND_SOURCE)==COMMAND_PIN,'frozen0-11 input/core changed')
    model,native=read(SOURCE),read(NATIVE);p=Compiler().compile(model);roster=read(ROOT/'packages/campaign/roster.reference.json')
    common.fixed_roster(roster) if hasattr(common,'fixed_roster') else __import__('tools.campaign_progress',fromlist=['fixed_roster']).fixed_roster(roster)
    stage_rows,population,origins,specials,controls=native_audit(native,model)
    enemy_rows=common.enemy_audit(native,model);prefab_rows,prefab_locks=enemy_sources(model,native)
    operator_rows,closures=common.operator_audit(p,roster)
    baseline_path=ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json';baseline=read(baseline_path)
    shared=[]
    for key in ('entities','abilities','buffs','selectors','rules','behaviors'):
        a={x['id']:x for x in baseline.get(key,[]) if '/enemy_' not in x['id']};b={x['id']:x for x in model.get(key,[]) if '/enemy_' not in x['id']}
        require(a==b,'operator common definition/behavior differs: '+key)
        shared.extend({'id':i,'kind':x['kind'],'sha256':identity(x)} for i,x in sorted(a.items()))
    old_contract=read(ROOT/'packages/mainline/contracts/main_00-10.json')
    required=[k for k in old_contract['required_mechanics'] if not k.startswith('stage:')]+[
        'stage:00-11_map_options_enemy_source','stage:00-11_native_timeline_controls_deadlines_offsets','stage:00-11_complete_checkpoint_replay']
    mechanism_refs={k:deepcopy(old_contract['mechanic_tests'].get(k,[])) for k in required if not k.startswith('stage:')}
    proposal={k:[dict(r,source_content_sha256=common.INPUT_SHA,target_content_sha256=PIN,applicability='pending_shared_witness_scope_review') for r in refs] for k,refs in mechanism_refs.items()}
    files=[SOURCE,NATIVE,COMMAND_SOURCE,baseline_path,ROOT/'packages/campaign/sources.00_11.reference.json',ROOT/'packages/campaign/controls.00_11.model.json',
        ROOT/'packages/campaign/enemies.00_11.attacks.json',ROOT/'packages/campaign/mainline_dependencies/level_main_00-11.json',ROOT/'packages/campaign/roster.reference.json',
        ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/operator_sources.lock.json',ROOT/'packages/campaign/enemy_sources.lock.json',
        ROOT/'tools/build_mainline_00_11_sources.py',ROOT/'tools/build_m12_mainline_00_11.py',Path(__file__)]
    locks=[lock(f) for f in files]+prefab_locks+common.raw_operator_locks();locks=list({x['path']:x for x in locks}.values())
    catalog=read(ROOT/'packages/campaign/mainline_catalog.json');native_row=next(r for r in catalog['stages'] if r['native_id']=='main_00-11')
    require(sum(r['selected'] for r in catalog['stages'])==36,'fixed campaign36 scope changed')
    for raw in native_row.get('original_binary_level_sources',[]):
        path=ROOT/raw['path'];require(sha(path)==raw['sha256'],'original raw0-11 source changed');locks.append(lock(path))
    client=deepcopy(old_contract['client_pending'])+[
        {'id':'00-11_managed_clear_negative_timeout_body','type':'client_pending','criterion':'Implemented3wave managed_clear/wait_for_clear model; native scheduler negative sentinel/method body not recovered'},
        {'id':'00-11_checkpoint_offset_axis_mapping','type':'client_pending','criterion':'Five actual MOVE offset copies(.44,.44) use declared row−y/col+x; native geometric comparator correspondence not measured'}]
    gaps={'model_gap':[],'client_pending':client,
        'witness_missing':[{'id':'00-11_specific_source_and_flow_witness','criterion':'New independent source/timeline/offset/deadline consumers require reviewer and actual source-specific event witness, not0-10flat evidence'},
            {'id':'00-11_full_three_way_completion','criterion':'37/0 continuous+checkpoint reported, command replay live; never consume unfinished report'}],
        'gate_contract_gap':[{'id':'shared_operator_witness_scope_not_approved','criterion':'Original0fb case inputSHA untouched; same definitions alone do not make it a0c execution. Exact effective fixture/seed/reachable rules/provider proof and reviewer needed; default cross-package gate still rejects'},
            {'id':'00-11_independent_source_receipt','criterion':'Draft is unreviewed, no independent approval or source check receipt created'},
            {'id':'00-11_synchronous_control_flag_review','criterion':'Native managed/blocks-wave flags are retained but current effects actions complete synchronously with no live membership. This transformation needs explicit independent model-flow review, not metadata self-proof.'}]}
    contract={'schema':'ark-sim/external-model-contract/v2','status':'draft_requires_independent_semantic_review','native_level_id':'level_main_00-11',
        'content_sha256':PIN,'native_source_sha256':NATIVE_PIN,'roster_frozen_sha256':roster['frozen_sha256'],
        'selected_skill_definitions':{r['character_id']:p.definitions['unit/'+r['character_id']]['metadata']['selected_skill_ability'] for r in roster['roster']},
        'required_mechanics':required,'mechanic_tests':{k:[] for k in required},'shared_witness_proposals':proposal,
        'native_spawn_by_definition':population,'pending_model_gaps':[],'source_review_pending':True,'typed_gaps':gaps,'client_pending':client,
        'source_audit':{'path':common.relative(AUDIT)},'formal_approval':False,'historical_package_metadata_preserved':True}
    sim=Engine.create(p,seed=123)
    audit={'schema':'ark-sim/00-11-external-source-audit/v1','status':'draft_unreviewed','formal_approval':False,'implementation_sha256':CORE,
        'content_sha256':PIN,'commands_sha256':COMMAND_PIN,'source_locks':locks,'field_audit':stage_rows+enemy_rows+prefab_rows+operator_rows,
        'population':population,'relative_timeline_origins':origins,'special_route_consumers':specials,'synchronous_control_profile_review':controls,
        'operator_definition_closures':closures,'shared_non_enemy_definitions':shared,'typed_gaps':gaps,
        'source_program_fingerprint':p.fingerprint,'source_runtime_fingerprint':sim.runtime_fingerprint,'model_seed_override':123,
        'scenario_seed_retained':p.scenario['seed'],'battle_bytes_unchanged':True,'metadata_draft_does_not_enter_battle':True}
    scope_path=ROOT/'packages/campaign/conversion_drafts/main_00-11.witness_scope.proposal.json'
    if scope_path.exists():
        contract['shared_witness_scope_proposal']={'path':common.relative(scope_path),'sha256':sha(scope_path),'status':'unapproved_not_executed_target_cases'}
        audit['shared_witness_scope_proposal']=deepcopy(contract['shared_witness_scope_proposal'])
    contract['source_audit']['sha256']=__import__('hashlib').sha256((json.dumps(audit,ensure_ascii=False,indent=2)+'\n').encode('utf8')).hexdigest()
    require(all(sha(ROOT/x['path'])==x['sha256'] for x in locks) and implementation_digest()==CORE,'source/core drift during audit')
    return contract,audit


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args();contract,audit=build()
    for target,source in ((CONTENT,SOURCE),(COMMANDS,COMMAND_SOURCE)):
        if args.check:require(target.exists() and target.read_bytes()==source.read_bytes(),'byte copy drift')
        else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
    for path,value in ((CONTRACT,contract),(AUDIT,audit)):
        if args.check:require(path.exists() and read(path)==value,'external draft source/output drift: '+str(path))
        else:write(path,value)
    print(json.dumps({'status':'draft_not_approved','native_spawns':sum(audit['population'].values()),'fields':len(audit['field_audit']),
        'shared_definitions':len(audit['shared_non_enemy_definitions']),'content_sha256':sha(CONTENT),'formal_approval':False}))


if __name__=='__main__':main()
