"""Prepare an auditable 0-10 conversion draft; never issue a review receipt."""
import argparse
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CORE = 'bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'
INPUT = ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json'
INPUT_SHA = '0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4'
COMMANDS = ROOT/'validation/campaign/m12_primary_00_10_full_20261002.commands.json'
COMMANDS_SHA = '4fe0c2f15121454bd7cef24d43c2eb148eabb07902f796671d51ae98382c2374'
CONTENT = ROOT/'packages/mainline/main_00-10.json'
COMMAND_OUTPUT = ROOT/'scenarios/mainline/main_00-10/commands.json'
AUDIT = ROOT/'packages/campaign/conversion_drafts/main_00-10.audit.json'
SCHEMA = ROOT/'packages/campaign/conversion_drafts/conversion_contract.schema.json'


def read(path): return json.loads(Path(path).read_bytes())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def identity(value):
    from ark_sim.contracts import thaw
    value=thaw(value)
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def relative(path): return Path(path).resolve().relative_to(ROOT).as_posix() if Path(path).resolve().is_relative_to(ROOT) else str(Path(path).resolve())
def require(condition, message):
    if not condition: raise ValueError(message)
def lock(path): return {'path':relative(path), 'sha256':sha(path)}


def leaves(value, pointer=''):
    if isinstance(value, Mapping) and value:
        for key, child in value.items(): yield from leaves(child,pointer+'/'+str(key).replace('~','~0').replace('/','~1'))
    elif isinstance(value, (list,tuple)) and value:
        for index, child in enumerate(value): yield from leaves(child,pointer+'/'+str(index))
    else: yield pointer,value


def record(source, pointer, value, status, consumer, criterion):
    return {'source_path':relative(source),'source_sha256':sha(source), 'native_pointer':pointer,
        'native_value_sha256':identity(value),'value':value,'classification':status,
        'consumer':consumer,'criterion':criterion,'pointer_kind':'json_pointer'}


def stage_audit(native, model, source):
    """Every native stage leaf receives a consumer or an explicit empty/default guard."""
    scene=model['scenarioDraft']; rows=len(native['mapData']['map']);cols=len(native['mapData']['map'][0])
    require(scene['map']['rows']==rows and scene['map']['cols']==cols,'map dimensions changed')
    build={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3};passing={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3}
    tiles=[]
    for row in native['mapData']['map']:
        require(len(row)==cols,'nonrectangular native map')
        for index in row:
            require(type(index) is int and 0<=index<len(native['mapData']['tiles']),'palette index invalid')
            t=native['mapData']['tiles'][index]
            require(set(t)=={'tileKey','heightType','buildableType','passableMask','playerSideMask','blackboard','effects'},'unclassified native tile field')
            require(t['playerSideMask']=='ALL','restricted native tile playerSideMask needs conversion')
            require(not t['blackboard'] and not t['effects'],'active native tile effects need conversion')
            tiles.append({k:deepcopy(v) for k,v in dict(t,buildableType=build[t['buildableType']],passableMask=passing[t['passableMask']]).items() if k!='playerSideMask'})
    require(scene['map']['tiles']==tiles,'matrix/palette/topdown conversion mismatch')
    option_map={'characterLimit':('parameters','deploy_capacity'),'maxLifePoint':('resources','life','initial'),
        'initialCost':('resources','dp','initial'),'maxCost':('resources','dp','capacity'),
        'costIncreaseTime':('resources','dp','recovery','interval_seconds')}
    for key, path in option_map.items():
        current=scene
        for part in path: current=current[part]
        require(current==native['options'][key],f'option consumer mismatch: {key}')
    require(scene['resources']['life']['capacity']==native['options']['maxLifePoint'],'life capacity not preserved')
    require(scene['resources']['dp']['recovery_rate']==1/native['options']['costIncreaseTime'],'DP recovery rate not preserved')
    speed=next(r for r in model['rules'] if r['id']==scene['rules']['movement.speed'])
    require(speed['parameters']['multiplier']==native['options']['moveMultiplier'],'move multiplier not consumed')
    require(native['options']['steeringEnabled'] is True,'steering disable profile needs new review')
    inactive_options={'reachableCheckIgnoreStartTile':False,'isTrainingLevel':False,'isHardTrainingLevel':False,
        'isPredefinedCardsSelectable':False,'displayRestTime':False,'maxPlayTime':-1.0,'functionDisableMask':'NONE','configBlackBoard':None}
    require(set(native['options'])==set(option_map)|{'moveMultiplier','steeringEnabled'}|set(inactive_options),'unknown native option')
    for key,value in inactive_options.items():require(native['options'][key]==value,f'active unsupported native option: {key}')
    empty_root={'environmentSe','tilesDisallowToLocate','optionalRunes','globalBuffs','extraRoutes','enemies','branches',
        'hardPredefines','excludeCharIdList','operaConfig','cameraPlugin'}
    for key in empty_root:require(not native[key],f'active native root field requires conversion: {key}')
    require(not any(native['predefines'].values()),'predefined actor/card requires conversion')
    require(all(not native['mapData'][k] for k in ('blockEdges','tags','effects','layerRects')),'active map extra needs conversion')
    require(all(r['difficultyMask']=='FOUR_STAR' for r in native['runes']),'rune applicable difficulty changed')
    require(model['manifest']['metadata']['inactive_native_runes']==native['runes'],'inactive difficulty1 runes changed')
    require(all(r['useDb'] is True and r['level']==0 and r['overwrittenData'] is None for r in native['enemyDbRefs']), 'enemy reference profile changed')
    cursor=0;expanded=[];controls=[];control_sources=[];used=set()
    for wi,wave in enumerate(native['waves']):
        require(set(wave)=={'preDelay','postDelay','maxTimeWaitingForNextWave','fragments','advancedWaveTag'},'unknown wave field')
        require(wave['maxTimeWaitingForNextWave']==-1 and wave['advancedWaveTag'] is None,'active wave gating requires converter')
        cursor+=wave['preDelay']
        for fi,fragment in enumerate(wave['fragments']):
            require(set(fragment)=={'preDelay','actions'},'unknown fragment field')
            start=cursor+fragment['preDelay'];end=start
            for ai,action in enumerate(fragment['actions']):
                defaults={'managedByScheduler':True,'blockFragment':False,'autoDisplayEnemyInfo':False,
                    'isUnharmfulAndAlwaysCountAsKilled':False,'hiddenGroup':None,'randomSpawnGroupKey':None,
                    'randomSpawnGroupPackKey':None,'randomType':'ALWAYS','refreshType':'ALWAYS','weight':0,
                    'dontBlockWave':False,'forceBlockWaveInBranch':False}
                require(set(action)==set(defaults)|{'actionType','key','count','preDelay','interval','routeIndex','autoPreviewRoute'},'unknown wave action field')
                for key,value in defaults.items():require(action[key]==value,f'active action option requires conversion: {key}')
                require(action['actionType'] in ('SPAWN','STORY','DISPLAY_ENEMY_INFO'),'unknown action type')
                require(type(action['autoPreviewRoute']) is bool,'invalid presentation-only route preview flag')
                if action['count']:end=max(end,start+action['preDelay']+(action['count']-1)*action['interval'])
                for repeat in range(action['count']):
                    at=start+action['preDelay']+repeat*action['interval']
                    if action['actionType']=='SPAWN':
                        expanded.append((at,'unit/'+action['key'],action['routeIndex'],wi,fi));used.add(action['routeIndex'])
                    else:
                        controls.append((at,action['actionType']));control_sources.append((deepcopy(action),wi,fi))
            cursor=end
        cursor+=wave['postDelay']
    require(len(expanded)==35 and len(scene['waves'])==35,'native spawn conservation not 35')
    require(Counter(x[1] for x in expanded)==Counter(w['definition'] for w in scene['waves']),'enemy population substitution')
    enemies={e['metadata']['native_id']:e for e in model['entities'] if 'enemy' in e.get('tags',[])}
    route_fields={'motionMode','startPosition','endPosition','spawnRandomRange','spawnOffset','checkpoints','allowDiagonalMove','visitEveryTileCenter','visitEveryNodeCenter','visitEveryCheckPoint'}
    check_fields={'type','time','position','reachOffset','randomizeReachOffset','reachDistance'}
    for native_route in native['routes']:
        require(set(native_route)==route_fields,'unknown route field')
    for actual,(at,definition,index,wi,fi) in zip(scene['waves'],expanded):
        route=deepcopy(native['routes'][index]);enemy=enemies[definition[5:]]
        require(route['motionMode'] in ('E_NUM','FLY' if 'flying' in enemy['tags'] else 'WALK'),'native route motion conflicts with DB entity or is unsupported')
        route['motionMode']='FLY' if 'flying' in enemy['tags'] else 'WALK'
        for key in ('startPosition','endPosition'):route[key]['row']=rows-1-route[key]['row']
        for cp in route.get('checkpoints') or []:
            require(set(cp)==check_fields,'unknown checkpoint field')
            require(cp['type'] in ('MOVE','WAIT_FOR_SECONDS'),'unconverted checkpoint action')
            require(not cp['randomizeReachOffset'] and not any(cp['reachOffset'].values()) and cp['reachDistance']==0,'active checkpoint geometry profile needs explicit converter')
            cp['position']['row']=rows-1-cp['position']['row']
        require(route==actual['route'],'route orientation/flags/checkpoints mismatch')
        require(at==actual['at_seconds'] and definition==actual['definition'],'spawn chronology/substitution mismatch')
        require(actual['position']==route['startPosition'],'spawn start position mismatch')
        place=actual['placement']
        require(place['offset']=={'row':-route['spawnOffset']['y'],'col':route['spawnOffset']['x']} and place['random_range']=={'row':route['spawnRandomRange']['y'],'col':route['spawnRandomRange']['x']},'spawn random extent/offset consumer mismatch')
        require(place['rule']=='rule/m7_spawn_rectangle' and place['stream']=='spawn' and place['sample_axes']==['col','row'] and place['sample_zero_range'] is False,'spawn distribution profile mismatch')
    require([(x['at_seconds'],x['effect']['event']) for x in scene['scheduledEffects']]==[(0,'native.control'),(49,'enemy.info_displayed')],'native control chronology changed')
    require(controls==[(0,'STORY'),(49,'DISPLAY_ENEMY_INFO')],'control source population changed')
    for actual,(action,wi,fi) in zip(scene['scheduledEffects'],control_sources):
        payload=actual['effect']['payload']
        require(payload['native_action']==action and payload['native_wave']==wi and payload['native_fragment']==fi,'native control payload/substitution mismatch')
        if action['autoPreviewRoute']:
            require(payload['native_preview_route']==native['routes'][action['routeIndex']],'native info preview route changed')
    rows_out=[]
    known_roots=set(native)
    expected_roots={'options','levelId','mapId','bgmEvent','environmentSe','mapData','tilesDisallowToLocate','runes','optionalRunes','globalBuffs','routes','extraRoutes','enemies','enemyDbRefs','waves','branches','predefines','hardPredefines','excludeCharIdList','randomSeed','operaConfig','cameraPlugin'}
    require(known_roots==expected_roots,'unclassified native root field')
    for pointer,value in leaves(native):
        top=pointer.split('/')[1]
        if top=='options':
            name=pointer.split('/')[2];status='inactive_value' if name in inactive_options else 'consumed_math'
            consumer='scenario.resources/parameters; movement.speed; spatial.steering'
            criterion='exact option values and consumer bindings asserted; nondefault unhandled options reject'
        elif top=='mapData':status='inactive_value' if pointer.endswith('/playerSideMask') or any(pointer.startswith('/mapData/'+k) for k in ('blockEdges','tags','effects','layerRects')) else 'consumed_math';consumer='scenario.map.tiles + GridTopology';criterion='exact matrix/palette masks/height/topdown equality; playerSideMask ALL guarded; active extra rejects'
        elif top=='routes':
            index=int(pointer.split('/')[2]);status='consumed_math' if index in used else 'inactive_value'
            consumer='scenario.waves[].route/placement; movement path/flying; preview payload for route10'
            criterion='used route converted exactly and enemy motion resolves E_NUM; unreferenced placeholders do not become executable routes'
        elif top=='waves':status='presentation_only' if pointer.endswith('/autoPreviewRoute') else 'consumed_math';consumer='scenario.waves[].at_seconds + scheduledEffects; preview retained as UI source';criterion='independent expansion of35SPAWN/1STORY/1INFO; unsupported combat flags rejected; preview has no headless combat effect'
        elif top=='enemyDbRefs':status='consumed_math';consumer='resolved enemy DB level0 + enemy definitions';criterion='useDb true/level0/no override asserted; pinned DB merge independently checked'
        elif top=='runes':status='inactive_value';consumer='manifest.metadata.inactive_native_runes';criterion='all FOUR_STAR inactive for difficulty1; unchanged exact list'
        elif top=='randomSeed':status='client_pending';consumer='scenario.seed explicit model seed123';criterion='native seed953816614 retained, mapping to model RNG not native-proven'
        elif top in {'bgmEvent','levelId','mapId'}:status='presentation_only';consumer='conversion audit source record';criterion='no headless combat math; native identity comes from catalog source binding'
        else:status='inactive_value';consumer='conversion guard';criterion='empty/null field asserted; nonempty rejects'
        rows_out.append(record(source,pointer,value,status,consumer,criterion))
    return rows_out


def enemy_audit(native, model):
    from tools.build_mainline_dependencies import resolve_enemy
    database_path=ROOT.parent/'unpack_work/campaign_tables/enemy_database.json'
    source_lock=read(ROOT/'packages/campaign/enemy_sources.lock.json')
    require(sha(database_path)==source_lock['sha256'],'enemy DB source lock mismatch')
    db=read(database_path);rows=[]
    attrs={'maxHp':'max_hp','atk':'atk','def':'def','magicResistance':'mres','moveSpeed':'move_speed','attackSpeed':'attack_speed_ratio','baseAttackTime':'attack_interval','massLevel':'mass_level'}
    for ref in native['enemyDbRefs']:
        resolved=resolve_enemy(db,ref)['resolved'];e=next(e for e in model['entities'] if e['id']=='unit/'+ref['id'])
        base=e['components']['attributes']['base']
        for key,target in attrs.items():require(abs(base[target]-resolved['attributes'][key]/(100 if key=='attackSpeed' else 1))<1e-9,f'enemy attribute changed: {ref["id"]}/{key}')
        for key in ('hpRecoveryPerSec','spRecoveryPerSec'):require(resolved['attributes'][key]==0,'enemy recovery needs conversion')
        require(resolved['attributes']['stunImmune'] is False,'enemy stun immunity needs conversion')
        require(set(resolved['attributes'])==set(attrs)|{'hpRecoveryPerSec','spRecoveryPerSec','stunImmune'},'unknown resolved enemy attribute')
        require(e['components']['lifecycle']['leak_loss']==resolved['lifePointReduce'],'native leak loss changed')
        require(('flying' if resolved['motion']=='FLY' else 'ground') in e['tags'],'native enemy motion changed')
        normal=e['components']['abilities']
        require(bool(normal)==(resolved['applyWay']!='NONE'),'passive enemy attack substitution')
        for pointer,value in leaves(resolved):
            if pointer in ('/name','/description'):status='presentation_only';consumer='source retained'
            elif pointer.startswith('/enemyTags'):status='inactive_value';consumer='source retained; no fixed12 effect filters these infection/drone tags'
            elif pointer in ('/attributes/hpRecoveryPerSec','/attributes/spRecoveryPerSec','/attributes/stunImmune'):status='inactive_value';consumer='zero recovery/false immunity guard'
            else:status='consumed_math';consumer=e['id']+'/components/attributes/resources/abilities/lifecycle/spatial'
            current=db[ref['id']][0]['enemyData'];parts=['',ref['id'],'0','enemyData']
            for part in pointer.split('/')[1:]:
                if isinstance(current,dict) and 'm_defined' in current:
                    require(current['m_defined'] is True,'level0 resolved field lacks an explicit source value');parts.append('m_value');current=current['m_value']
                parts.append(part);current=current[int(part)] if isinstance(current,list) else current[part]
            if isinstance(current,dict) and 'm_defined' in current:
                require(current['m_defined'] is True,'level0 resolved field lacks an explicit source value');parts.append('m_value');current=current['m_value']
            require(current==value,'resolved field pointer does not prove source value')
            item=record(database_path,'/'.join(parts),value,status,consumer,'DB m_defined false inherits / true zero overrides; level0 and stage override resolved before exact attribute checks')
            item['derived_resolved_pointer']='/'+ref['id']+'/resolved'+pointer;rows.append(item)
    return rows


def prefab_audit(model):
    """Account for serialized enemy combat and mover fields, with real asset hashes."""
    rows=[];asset_locks=[]
    attack_path=ROOT/'packages/campaign/enemies.00_10.attacks.json';attack=read(attack_path)
    frames_path=ROOT.parent/'data/tables/effect_frames.json';frames=read(frames_path)['enemies']
    require(sha(frames_path)==attack['manifest']['metadata']['frames_sha256'],'enemy frame source hash changed')
    require(model['manifest']['metadata']['enemy_model']['native_enemy_records']==attack['manifest']['metadata']['native_enemy_records'],'enemy raw component references changed')
    for item in attack['manifest']['metadata']['native_enemy_records']:
        source=item['source'];asset=ROOT.parent/source['source'];require(sha(asset)==source['source_sha256'],'enemy prefab source bytes changed');asset_locks.append(lock(asset))
        fields=source['combat_fields'];identifier=item['native_id']
        if not item['passive']:
            ability=next(a for a in model['abilities'] if a['id']==f'ability/{identifier}/normal_attack')
            ev=[e for e in frames[identifier]['anims'][fields['_animKey']]['ev'] if e['n']=='OnAttack']
            expected=[{'at_seconds':e['f']/30,'effect':{'op':'damage','scale':fields['_atkScale'],'damage_type':{1:'physical',2:'arts',3:'true'}[fields['_damageType']]}} for e in ev]
            require(ability['timeline']==expected,'native enemy frame/scale/type conversion mismatch')
        require(not fields.get('_activeBuffs') and not fields.get('_projectileKey'),'enemy active buff/projectile missing converter')
        for pointer,value in leaves(fields):
            if item['passive']:classification='inactive_value';consumer='applyWay NONE: no normal attack attached; combat component retained as source'
            elif pointer=='/m_Enabled':
                require(value==1,'disabled enemy combat component needs conversion')
                classification='consumed_math';consumer='active native combat component mapped to owned normal ability'
            elif pointer.startswith(('/m_','/_metadata')):classification='presentation_only';consumer='exact native component/script pointer evidence'
            elif pointer.startswith(('/_atkScale','/_damageType','/_animKey')):classification='consumed_math';consumer=f'ability/{identifier}/normal_attack.timeline'
            elif pointer in ('/_activeBuffs','/_projectileKey'):classification='inactive_value';consumer='no native on-hit Buff/projectile in this enemy subset'
            else:classification='client_pending';consumer='explicit blocked-target/unscaled-frame/cooldown-state-clock model; original native callback/selection/mode implementation pending'
            r=record(asset,f'/combat/{source["combat_path_id"]}'+pointer,value,classification,consumer,'serialized fields retained exactly; actual authored frame/scale/type checked; remaining nondefault FSM flags do not self-prove native methods');r['pointer_kind']='unity_object_pathid_and_typetree_field';rows.append(r)
    spatial_path=ROOT/'packages/campaign/spatial.profiles.json';spatial=read(spatial_path)
    for identifier,item in spatial['raw_enemy_movers']['enemies'].items():
        asset=ROOT.parent/item['source']['path'];require(sha(asset)==item['source']['sha256'],'enemy mover source bytes changed');asset_locks.append(lock(asset))
        entity=next(e for e in model['entities'] if e['id']=='unit/'+identifier)
        parameters=entity['components']['spatial']['steering']['parameters']
        require(parameters['response_factor']==item['fields']['_steeringFactor'] and parameters['max_acceleration']==item['fields']['_maxSteeringForce'],'steering parameters missing source mapping')
        for pointer,value in leaves(item['fields']):
            status='client_pending' if pointer=='/_halfBodyWidth' else 'consumed_math'
            r=record(asset,f'/mover/{item["component_path_id"]}'+pointer,value,status,'bounded steering response/acceleration; declared point-body topology','response constants consumed exactly; native body-width/separation equation is not recovered, point-body is explicit model profile');r['pointer_kind']='unity_object_pathid_and_typetree_field';rows.append(r)
    asset_locks.extend([lock(frames_path),lock(spatial_path)])
    return rows,asset_locks


def load_evidence(path, package_sha):
    d=read(path);cases=d.get('cases',{})
    passed=d.get('passed') is True
    same_core=d.get('implementation_sha256')==CORE
    same_input=(d.get('input_package_sha256') or d.get('package_sha256'))==package_sha
    tests=d.get('tests',[])
    test_valid=bool(tests) and all(t.get('result')=='passed' and (ROOT/t['path']).exists() and sha(ROOT/t['path'])==t['source_sha256'] for t in tests)
    return {'path':relative(path),'sha256':sha(path),'schema':d.get('schema'),'passed':passed,
        'implementation_sha256':d.get('implementation_sha256'),'input_package_sha256':d.get('input_package_sha256') or d.get('package_sha256'),
        'current_case_eligible':passed and same_core and same_input and test_valid,
        'tests':tests,'case_ids':list(cases) if isinstance(cases,dict) else [c['case'] for c in cases],
        'classification':'executed_current_model' if passed and same_core and same_input and test_valid else 'historical_or_incomplete_identity'}


def operator_audit(program, roster):
    from ark_sim.contracts import thaw
    normalized_path=ROOT/'packages/campaign/operators.normalized.json'
    normalized={x['character_id']:x for x in read(normalized_path)['operators']}
    normalized_index={x['character_id']:i for i,x in enumerate(read(normalized_path)['operators'])}
    stat_map={'maxHp':'max_hp','atk':'atk','def':'def','magicResistance':'mres','baseAttackTime':'attack_interval',
        'moveSpeed':'move_speed','blockCnt':'block_count','cost':'deploy_cost','respawnTime':'redeploy_time','massLevel':'mass_level'}
    bb_consumer={
        'myrtle':'S2 periodic one-target .5ATK heal and DP1×16 plus duration/interval; native selector range x-4',
        'bpipe':'S3 direct_ratio ATK/DEF1.2, attack_interval ratio+.7, block_count+1; native frames14/17/20',
        'chen':'S1 attack scale3.2 and stun1.5; exact selected freeze + normal attack event driver',
        'liskam':'S1 DEF ratio1 and8s duration, receiver one-charge settlement override; positiveHP SP model',
        'demkni':'S3 .35ATK heal, movement slow-.6, arts incoming multiplier1.55; fake.b is description formatting only',
        'plosis':'S2 flat attack_interval−2.1 and range y-7/limit3; fixed source-preDelay state-clock profile',
        'angel':'S3 attack scale1.1/times5/interval−.11; captured windup AS1.12 with independent repeat spacing',
        'amgoat':'S3 direct_ratio ATK1.3/interval−1.1/max_targets1+5=6; dynamic random selector and source clock model',
        'kalts':'host trigger owned token;20s linear_remaining ATK2.6/DEF2/true damage; noKill selfHP.5 penalty',
        'lisa':'S3 .2ATK regeneration; passive fragility .2→S3 .4 source-bound group; duration35/range y-8',
        'weedy':'S3 scale3.5/force3/8s ledger damage1200 per grid/interval.066; declared forced-motion/EXTEND profile',
        'cgbird':'S3 ATK+.8/RES+1.5/arts dodge.25; source Attack_C mapping/range y-4/three-target model'}
    rows=[];closures=[]
    for reference in roster['roster']:
        cid=reference['character_id'];n=normalized[cid];unit=program.definitions['unit/'+cid];base=unit['components']['attributes']['base']
        require(n['config']==reference['config'],'normalized profile changed')
        for src,target in stat_map.items():require(base[target]==n['stats']['model_stats'][src],f'operator source attribute differs: {cid}/{src}')
        require(base['attack_speed_ratio']==n['stats']['model_stats']['attackSpeed']/100,'operator AS mapping changed')
        level=n['selected_skill']['level'];sp=level['spData'];ability=program.definitions[unit['metadata']['selected_skill_ability']]
        require(unit['components']['resources']['sp']['initial']==sp['initSp'] and unit['components']['resources']['sp']['capacity']==sp['spCost'],'selected SP definition differs')
        require(any(c['resource']=='sp' and c['amount']==sp['spCost'] for c in ability['activation']['costs']),'selected SP payment differs')
        require(sp['maxChargeTime']==1 and sp['increment']==1,'unsupported selected SP charge/increment')
        reached=set();pending=[unit['id']]
        while pending:
            identifier=pending.pop()
            if identifier in reached:continue
            reached.add(identifier)
            for _,value in leaves(program.definitions[identifier]):
                if isinstance(value,str) and value in program.definitions and value not in reached:pending.append(value)
        selected_talents=[{'slot_index':t['slot_index'],'selected_candidate':t['selected_candidate']} for t in n['talents'] if t['selected_candidate'] is not None]
        closures.append({'character_id':cid,'config':reference['config'],'normal_ability_ids':[a for a in unit['components']['abilities'] if a!=ability['id']],
            'selected_ability':ability['id'],'initial_talent_buffs':thaw(unit['components'].get('buffs',{}).get('initial',[])),
            'selected_source_talents':selected_talents,'reachable_definition_identities':[{'id':i,'kind':program.definitions[i]['kind'],'sha256':identity(program.definitions[i])} for i in sorted(reached)],
            'evidence_meaning':'Definition ownership/reference closure and source config/attributes/SP assertions; does not self-prove every talent execution or native completeness.'})
        for pointer,value in leaves(level):
            status='presentation_only' if pointer.startswith(('/name','/description','/levelUpCost','/spData/levelUpCost')) else 'consumed_math'
            if pointer.startswith('/blackboard/'):
                index=int(pointer.split('/')[2])
                if level['blackboard'][index]['key']=='fake.b':status='presentation_only'
            rows.append(record(normalized_path,f'/operators/{normalized_index[cid]}/selected_skill/level'+pointer,value,status,
                ability['id']+'; '+bb_consumer[cid.split('_')[-1]],'Source selected native_level_index9 and exact SP/profile checked; detailed BB consumers require independent review of referenced definition/source graphs'))
    return rows,closures


def raw_operator_locks():
    """Check actual raw-table/prefab/template/token bytes, beyond package metadata."""
    found={}
    def add(path,expected):
        path=Path(path);require(path.exists() and sha(path)==expected,'raw operator dependency missing/changed: '+str(path))
        found[relative(path)]=lock(path)
    for source in read(ROOT/'packages/campaign/operator_sources.lock.json')['files'].values():add(ROOT/source['path'],source['sha256'])
    add(ROOT.parent/'unpack_work/campaign_tables/enemy_database.json',read(ROOT/'packages/campaign/enemy_sources.lock.json')['sha256'])
    story=read(ROOT/'packages/campaign/controls.00_10.reference.json');add(ROOT/story['path'],story['sha256'])
    support=read(ROOT/'packages/campaign/talents.support.json')['manifest']['metadata']['source_evidence']
    for cid,row in support['operators'].items():
        paths=[p for p in (ROOT.parent/'data/charpack').glob(cid+'.ab_unpacked/CAB-*') if p.is_file() and p.suffix!='.resS']
        matches=[p for p in paths if sha(p)==row['charpack_sha256']]
        require(len(matches)==1,'support exact charpack raw locator ambiguous/missing: '+cid);add(matches[0],row['charpack_sha256'])
    add(ROOT.parent/'data/anon_textassets/buff_template_data.dat',support['buff_template_source_sha256'])
    add(ROOT.parent/'data/anon_textassets/buff_table352282.dat',support['buff_database']['source_sha256'])
    token_source=support['mon3tr_external_attack_overrides']['native_source']['source']
    add(ROOT.parent/'unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab',token_source['sha256'])
    # Sources with explicit exact locators in frozen attack/frame/skill subsets.
    def walk(value):
        if isinstance(value,dict):
            for a,b in [('path','sha256'),('source','source_sha256'),('source_path','source_sha256')]:
                if isinstance(value.get(a),str) and isinstance(value.get(b),str) and len(value[b])==64:
                    candidates=[Path(value[a]),ROOT/value[a],ROOT.parent/value[a]]
                    existing=next((p for p in candidates if p.is_file()),None)
                    require(existing is not None,'declared raw dependency has no actual locator: '+value[a])
                    add(existing,value[b])
            for child in value.values():walk(child)
        elif isinstance(value,list):
            for child in value:walk(child)
    paths=[ROOT/'packages/campaign/talents.attack.json',ROOT/'packages/campaign/animation_bindings.reference.json']+sorted((ROOT/'packages/campaign').glob('skills.*.json'))
    for path in paths:walk(read(path))
    return list(found.values())


def primary_suite_mapping():
    """Map finite canonical nodes to the completed full-suite/source inventory.

    Case IDs are reconstructed from the exact imported helper source. This is
    not a claim that pytest -q saved a per-node event ledger or source-start SHA.
    """
    export_path=ROOT/'validation/campaign/m12_primary_tests_review_format_20261002.json'
    execution_path=ROOT/'validation/campaign/m12_primary_test_execution_20261002.json'
    run_path=ROOT/'validation/campaign/m12_primary_full_tests_20261002.json'
    exported,execution,run=read(export_path),read(execution_path),read(run_path)
    require(exported['passed'] and execution['passed'] and run['passed'],'primary suite did not complete successfully')
    require(exported['implementation_sha256']==CORE==run['implementation_before']==run['implementation_after'],'primary suite implementation identity mismatch')
    require(execution['input_package_sha256']==INPUT_SHA and execution['exit_code']==0,'primary suite package/exit mismatch')
    require(exported['source_execution_sha256']==sha(execution_path) and execution['run_evidence_sha256']==sha(run_path),'primary suite exporter identity mismatch')
    require(sha(ROOT/execution['log'])==execution['log_sha256']==exported['log_sha256'],'primary suite log changed')
    require(exported['tests_passed']==1133 and 'skip' not in execution['summary'].lower(),'primary suite count/skip scope changed')
    inventory=execution['test_sources_at_completion']
    for path,digest in inventory.items():require(sha(ROOT/path)==digest,'completion source inventory changed: '+path)
    environment={key:os.environ.get(key) for key in ('CAMPAIGN_MECHANISM_PACKAGE','CAMPAIGN_SUMMON_PACKAGE')}
    for key in environment:os.environ[key]=str(INPUT)
    groups=[('test_canonical_roster_trio','witness_canonical_roster_trio',None,20),
        ('test_canonical_night','witness_canonical_night','cgbird',13),
        ('test_canonical_weedy','witness_canonical_weedy','weedy',10),
        ('test_canonical_kalts','witness_canonical_kalts','kalts',15)]
    rows=[];witnesses={}
    try:
        for test_name,helper_name,operator,count in groups:
            test_path='tests_v2/'+test_name+'.py';helper_path='tools/'+helper_name+'.py'
            require(test_path in inventory and helper_path in inventory,'canonical test/helper absent from completed suite inventory')
            module=importlib.import_module('tools.'+helper_name)
            require(Path(module.__file__).resolve()==(ROOT/helper_path).resolve(),'canonical helper import path mismatch')
            require(len(module.CASES)==count,'canonical source case inventory changed')
            for case in module.CASES:
                actor=operator or ('liskam' if case.startswith('lisk_') else 'chen' if case.startswith('chen_') else 'lisa' if case.startswith('lisa_') else 'fixed12')
                node=test_path+'::test_canonical_mechanism['+case+']'
                ref={'path':relative(export_path),'sha256':sha(export_path),'case':case,'test_node_id':node,
                    'test_source_sha256':inventory[test_path],'helper_path':helper_path,'helper_sha256':inventory[helper_path],
                    'actual_execution':relative(execution_path),'actual_execution_sha256':sha(execution_path),
                    'input_package_sha256':INPUT_SHA,'implementation_sha256':CORE,
                    'scope':'all-pass/no-skip full-suite plus exact source finite CASES; individual event export and source-start guard not claimed'}
                rows.append(dict(ref,operator=actor));witnesses['operator:'+actor+'/'+case]=[ref]
        test_path='tests_v2/test_canonical_lisk_defense.py';helper_path='tools/witness_canonical_lisk_defense.py'
        require(test_path in inventory and helper_path in inventory,'Liskam DEF test/helper absent from completed suite')
        ref={'path':relative(export_path),'sha256':sha(export_path),'case':'canonical_defense_is_double_then_expires_before_tick240_hit',
            'test_node_id':test_path+'::test_canonical_defense_is_double_then_expires_before_tick240_hit','test_source_sha256':inventory[test_path],
            'helper_path':helper_path,'helper_sha256':inventory[helper_path],'actual_execution':relative(execution_path),'actual_execution_sha256':sha(execution_path),
            'scope':'completed full suite source-at-completion inventory; no per-node event export/source-start claim'}
        rows.append(dict(ref,operator='liskam'));witnesses['operator:liskam/'+ref['case']]=[ref]
    finally:
        for key,value in environment.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    return rows,witnesses,[lock(export_path),lock(execution_path),lock(run_path)]


def build():
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.campaign_progress import fixed_roster,execution_gate
    require(implementation_digest()==CORE,'conversion source runtime changed')
    require(sha(INPUT)==INPUT_SHA and sha(COMMANDS)==COMMANDS_SHA,'frozen model input/commands changed')
    model=read(INPUT);native_path=ROOT/'packages/campaign/native_reference/level_main_00-10.json';native=read(native_path)
    roster_path=ROOT/'packages/campaign/roster.reference.json';roster=read(roster_path);ids=fixed_roster(roster)
    catalog=read(ROOT/'packages/campaign/mainline_catalog.json')
    require(sum(s['selected'] for s in catalog['stages'])==36,'campaign scope changed')
    stage=next(s for s in catalog['stages'] if s['native_id']=='main_00-10')
    require(stage['level_id']=='level_main_00-10' and stage['dependency_summary']['declared_spawn_count']==35,'catalog stage identity changed')
    program=Compiler().compile(model)
    selected={};configs=[]
    for row in roster['roster']:
        unit=program.definitions['unit/'+row['character_id']]
        require(unit['metadata']['config']==row['config'],'fixed profile mismatch')
        ability=unit['metadata']['selected_skill_ability']
        require(ability in unit['components']['abilities'] and program.definitions[ability]['metadata']['native_skill_id']==row['config']['skill_id'],'selected skill substituted/not owned')
        selected[row['character_id']]=ability;configs.append({'character_id':row['character_id'],'config':deepcopy(row['config']),'selected_ability':ability})
    prefab_rows,prefab_locks=prefab_audit(model)
    operator_rows,operator_closures=operator_audit(program,roster)
    audit_rows=stage_audit(native,model,native_path)+enemy_audit(native,model)+prefab_rows+operator_rows
    coverage_path=ROOT/'validation/campaign/m12_deployed_case_coverage.json';coverage=read(coverage_path)
    require(coverage['implementation_sha256']==CORE and coverage['input_package_sha256']==INPUT_SHA,'deployed case coverage identity stale')
    witnesses={};evidence={}
    for key,references in coverage['requirements'].items():
        validated=[]
        for ref in references:
            path=ROOT/ref['path'];require(sha(path)==ref['sha256'],'coverage evidence hash changed')
            ev=load_evidence(path,INPUT_SHA);evidence[ref['path']]=ev
            require(ev['current_case_eligible'] and ref['case'] in ev['case_ids'],'case declaration is not current executed evidence')
            validated.append(deepcopy(ref))
        witnesses['operator:'+key]=validated
    history=['canonical_trio_witness.m8_roster.json','canonical_night_witness.m8_targeting_v2.json','canonical_weedy_witness.m8_roster.json','canonical_kalts_witness.m10_f6bb.json']
    for name in history:
        path=ROOT/'validation/campaign'/name;evidence[relative(path)]=load_evidence(path,INPUT_SHA)
    kalts_boundary=ROOT/'validation/campaign/kalts_boundaries_m12_final_20261002.json'
    if kalts_boundary.exists():
        boundary_evidence=load_evidence(kalts_boundary,INPUT_SHA);evidence[relative(kalts_boundary)]=boundary_evidence
        if boundary_evidence['current_case_eligible']:
            for case_id in boundary_evidence['case_ids']:
                witnesses['operator:kalts/'+case_id]=[{'path':relative(kalts_boundary),'sha256':sha(kalts_boundary),'case':case_id,'required_event_types':['damage.accepted']}]
    suite_rows,suite_witnesses,suite_locks=primary_suite_mapping();witnesses.update(suite_witnesses)
    angel_boundary=ROOT/'validation/campaign/angel_blessing_damage_m12_final_20261002.json'
    if angel_boundary.exists():
        ev=load_evidence(angel_boundary,INPUT_SHA);evidence[relative(angel_boundary)]=ev
        require(ev['current_case_eligible'],'angel boundary evidence stale')
        for case_id in ev['case_ids']:witnesses['operator:angel/'+case_id]=[{'path':relative(angel_boundary),'sha256':sha(angel_boundary),'case':case_id,'required_event_types':['damage.accepted']}]
    client=[{'id':key,'type':'client_pending','criterion':text} for key,text in {
        'native_rng_seed_and_draws':'Native953816614 retained; explicit model123, SHA-derived MT, uniform-rectangle draws and selectors are complete models without client RNG alignment.',
        'native_route_collision_and_steering':'half-up grid/8neighbor/no-corner/point-body/clipped steering/own-blocked are declared mathematical policies; original native comparator/body/method bodies pending.',
        'native_actor_attack_clocks':'Source frames retained; fixed timing/spacing/cadence/state clocks and hit travel explicitly defined; original FSM callbacks and Ptilopsis native signal cadence pending.',
        'external_token_source_versions':'Exact2025 token bundle MD5/SHA/Animator/Spine evidence consumed; correspondence with2026 local charpack/client not established.',
        'native_heal_priority64':'self/ownMon/foreign mathematical preference profile consumed; original enum64 method body and comparator not recovered.',
        'native_shield_damage_event_order':'positive HP damage gates defense/talent SP; block all three types source-backed; native ON_TAKE_DAMAGE order pending.',
        'native_weedy_empty_forward':'Empty-target pays/no-forward declared model; native forward projectile rule/physics trajectory pending.',
        'native_UI_pause_callbacks':'STORY emits lock and commands then zero-game-time ack; native wall-time pause/UI callback order and presentation text encoding not combat-math validation.'}.items()]
    missing=[{'id':'formal_content_three_way_stage','type':'witness_missing','criterion':'Adding metadata changes content/program fingerprint. New planned_content/commands must execute35spawn, exact5enemies, legal commands, victory, checkpoint and replay under this new identity. Original0fb stage run is separate and its checkpoint/replay must actually finish.'}]
    gates=[{'id':'independent_native_field_review','type':'gate_contract_gap','criterion':'This builder asserts field consumers but cannot approve its own native_fields_verified or external conversion review.'},
        {'id':'external_conversion_receipt','type':'gate_contract_gap','criterion':'Independent receipt must bind full case_inputs/content/commands/roster/runtime/native_source and executed tests, after reviewer checks.'},
        {'id':'suite_node_source_mapping_review','type':'gate_contract_gap','criterion':'59 canonical nodes are mapped from exact completed-suite module/helper inventory; reviewer must confirm all-pass/no-skip selection and root launch PACKAGE environments. Source hashes are at completion, not source-start; no synthetic per-node actual event ledger is invented.'}]
    source_files=[INPUT,COMMANDS,native_path,roster_path,ROOT/'packages/campaign/mainline_catalog.json',ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/operator_sources.lock.json',ROOT/'packages/campaign/enemy_sources.lock.json',ROOT/'packages/campaign/controls.00_10.reference.json',ROOT/'packages/campaign/controls.00_10.model.json',ROOT/'packages/campaign/enemies.00_10.attacks.json',ROOT/'packages/campaign/animation_bindings.reference.json',ROOT/'tools/campaign_progress.py',Path(__file__),coverage_path]
    source_files += sorted((ROOT/'packages/campaign').glob('skills.*.json'))
    source_files += [ROOT/'packages/campaign/talents.attack.json',ROOT/'packages/campaign/talents.support.json',SCHEMA,
        ROOT/'tools/validate_first_model_conversion.py',ROOT/'tools/experiments/first_model_conversion/test_contract.py']
    raw_stage=ROOT.parent/'unpack_work/release_20260831/base_raw/level_main_00-10.dat';source_files.append(raw_stage)
    require(sha(raw_stage)==stage['original_binary_level_sources'][0]['sha256'],'raw stage source changed')
    locks=[lock(p) for p in source_files]+prefab_locks+raw_operator_locks()+suite_locks
    locks=list({x['path']:x for x in locks}.values())
    required=list(witnesses)+['selected_skill:'+r['config']['skill_id'] for r in roster['roster']]+['stage:map_routes_wave_control_enemy_conservation','stage:complete_checkpoint_replay']
    for row in roster['roster']:
        character=row['character_id'];alias=character.split('_')[-1]
        references=[ref for key,refs in witnesses.items() if key.startswith('operator:'+alias+'/') for ref in refs]
        witnesses['selected_skill:'+row['config']['skill_id']]=references
    blockers=missing+gates
    contract={'schema':'ark-sim/first-model-conversion-contract/v1','status':'conversion_draft_not_approved','native_level_id':'level_main_00-10','native_id':'main_00-10','difficulty':1,
        'fixed_roster':configs,'roster_frozen_sha256':roster['frozen_sha256'],'selected_skill_definitions':selected,'native_spawn_count':35,'native_enemy_count':5,
        'native_fields_verified':False,'pending_mechanics':[x['id'] for x in blockers],
        'required_mechanics':required,'mechanic_tests':witnesses,'typed_gaps':{'model_gap':[],'client_pending':client,'witness_missing':missing,'gate_contract_gap':gates},
        'source_locks':locks,'source_audit':{'path':relative(AUDIT),'field_count':len(audit_rows)},
        'implementation_sha256':CORE,'model_source_sha256':INPUT_SHA,'commands_source_sha256':COMMANDS_SHA,
        'planned_content':relative(CONTENT),'planned_commands':relative(COMMAND_OUTPUT),'formal_approval':False,'review_receipt':False,
        'original_pending_preserved':{'scenario':deepcopy(model['scenarioDraft']['metadata'].get('pending_conversion',[])),'manifest':deepcopy(model['manifest']['metadata'].get('pending',[]))}}
    result=deepcopy(model);result['status']='conversion_draft_not_approved';result['manifest']['id']='package/mainline/main_00-10/conversion-draft';result['manifest']['metadata']['conversion_contract_draft']=True
    result['scenarioDraft']['metadata']['campaign']=contract
    new_program=Compiler().compile(result)
    require(all(program.definitions[k]==new_program.definitions[k] for k in program.definitions if program.definitions[k]['kind']!='scenario'),'contract builder changed canonical definition')
    old_scene=deepcopy(model['scenarioDraft']);new_scene=deepcopy(result['scenarioDraft'])
    old_scene.pop('metadata');new_scene.pop('metadata')
    require(old_scene==new_scene,'contract builder changed executable scene outside metadata')
    case={'level_id':'level_main_00-10','native_id':'main_00-10','expected_native_spawns':35}
    try:execution_gate(new_program,case,roster)
    except ValueError as error: gate_error=str(error)
    else:raise ValueError('unapproved draft unexpectedly passed execution gate')
    audit={'schema':'ark-sim/first-model-source-field-audit/v1','status':'draft_requires_independent_review','formal_approval':False,
        'implementation_sha256':CORE,'model_source_sha256':INPUT_SHA,'source_locks':locks,'field_audit':audit_rows,'classification_counts':dict(Counter(r['classification'] for r in audit_rows)),
        'mechanism_evidence':list(evidence.values()),'primary_suite_node_source_mapping':suite_rows,
        'operator_definition_closures':operator_closures,'typed_gaps':contract['typed_gaps'],'old_audit_is_history':'docs/campaign/C0_FIRST_MODEL_ACCEPTANCE_MATRIX.md',
        'base_program_fingerprint':program.fingerprint,'draft_program_fingerprint':new_program.fingerprint,'definitions_exactly_preserved':True,'execution_gate_rejected_draft':gate_error,
        'planned_content':relative(CONTENT),'planned_commands':relative(COMMAND_OUTPUT)}
    require(implementation_digest()==CORE,'runtime changed during conversion audit')
    require(all(sha(ROOT/x['path'])==x['sha256'] for x in locks),'source changed during conversion audit')
    return result,read(COMMANDS),audit


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    content,commands,audit=build()
    for path,value in [(CONTENT,content),(COMMAND_OUTPUT,commands),(AUDIT,audit)]:
        if args.check:
            require(path.exists() and read(path)==value,f'conversion draft changed: {relative(path)}')
            if path==COMMAND_OUTPUT:require(sha(path)==COMMANDS_SHA,'planned commands must preserve source bytes')
        elif path==COMMAND_OUTPUT:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(COMMANDS.read_bytes())
        else:write(path,value)
    print(json.dumps({'status':'draft_not_approved','fields':len(audit['field_audit']),'gate_rejection':audit['execution_gate_rejected_draft']}))


if __name__=='__main__':main()
