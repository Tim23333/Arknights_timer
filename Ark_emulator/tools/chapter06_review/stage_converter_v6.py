"""Source-bound activation and exceptional exit conversion, preserving strict v5 checks.

Requires explicit exact enemy bindings and implemented tile profiles. No
unknown action, rune, predefine or terrain becomes a silent no-op.
"""
from collections import Counter
from copy import deepcopy


def route_ir(route,rows):
    result=deepcopy(route)
    def top(position):return {'row':rows-1-position['row'],'col':position['col']}
    result['startPosition']=top(route['startPosition']);result['endPosition']=top(route['endPosition'])
    result['checkpoints']=result.get('checkpoints') or []
    for checkpoint in result['checkpoints']:
        if checkpoint.get('position') is not None:checkpoint['position']=top(checkpoint['position'])
    return result


def map_plan(native):
    grid=native['mapData']['map'];palette=native['mapData']['tiles']
    if not grid or not grid[0] or any(len(row)!=len(grid[0]) for row in grid):raise ValueError('Rectangular native map required')
    build={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3};passing={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3};tiles=[]
    for row in grid:
        for index in row:
            if type(index) is not int or not 0<=index<len(palette):raise ValueError('Native palette index invalid')
            tile=palette[index]
            if tile['buildableType'] not in build or tile['passableMask'] not in passing:raise ValueError('Unknown native tile mask')
            tiles.append({'tileKey':tile['tileKey'],'buildableType':build[tile['buildableType']],'passableMask':passing[tile['passableMask']],
                          'heightType':tile['heightType'],'blackboard':deepcopy(tile.get('blackboard')),'effects':deepcopy(tile.get('effects'))})
    return {'rows':len(grid),'cols':len(grid[0]),'tiles':tiles,'coordinate_conversion':'map rows are top-down; native route row -> rows-1-row'}


MASKS={'NONE':0,'NORMAL':1,'FOUR_STAR':2,'EASY':4,'SIX_STAR':8,'ALL':15}


def compose(native,native_id,bindings,tile_profiles,seed=None,story_controls=None,predefined_profile=None,*,story_key_profile=None,action_lifecycle_profiles=None):
    from tools.chapter06_review.story_keys_v5 import validate
    story_bindings=validate(native,native_id,story_key_profile)
    profiles=action_lifecycle_profiles or []
    if not isinstance(profiles,list):raise ValueError('Explicit lifecycle profiles list required')
    provided={};consumed=set()
    for profile in profiles:
        if not isinstance(profile,dict) or set(profile)!={'native_id','wave','fragment','action','native_action','lifecycle'}:
            raise ValueError('Exact source lifecycle profile fields required')
        ident=tuple(profile[k] for k in ('wave','fragment','action'))
        if any(type(v) is not int or v<0 for v in ident) or ident in provided:
            raise ValueError('Unique strict lifecycle action location required')
        provided[ident]=profile

    from ark_sim.domains.tile_mechanics import validate_profiles
    validate_profiles(tile_profiles)
    for key in ('branches','globalBuffs','hardPredefines'):
        if native.get(key):raise ValueError('Reference stage requires explicit '+key+' conversion')
    has_predefines=any(native.get('predefines',{}).get(k) for k in ('characterInsts','tokenInsts','characterCards','tokenCards'))
    if has_predefines:
        if not isinstance(predefined_profile,dict) or set(predefined_profile)!={'native_predefines','initial_entities','card_bindings','resources'}:
            raise ValueError('Reference stage predefines require exact native initial/card/resource profile')
        if predefined_profile['native_predefines']!=native['predefines']:raise ValueError('Predefined profile native data mismatch')
        aliases=set()
        for bucket in ('characterInsts','tokenInsts'):
            for record in native['predefines'].get(bucket) or []:
                if type(record.get('hidden')) is not bool:
                    raise ValueError('Native predefined hidden flag must be strict boolean')
                alias=record.get('alias')
                if alias is not None:
                    if not isinstance(alias,str) or not alias or alias in aliases:
                        raise ValueError('Native predefined aliases must be globally unique nonempty strings')
                    aliases.add(alias)
        for bucket in ('characterInsts','tokenInsts'):
            records=native['predefines'].get(bucket) or []
            matches=[r for r in predefined_profile['initial_entities'] if r.get('parameters',{}).get('native_bucket')==bucket]
            if len(records)!=len(matches) or any(matches[i].get('parameters',{}).get('native_instance')!=record for i,record in enumerate(records)):
                raise ValueError('Native predefined instance consumer incomplete')
        for bucket in ('characterCards','tokenCards'):
            records=native['predefines'].get(bucket) or []
            matches=[r for r in predefined_profile['card_bindings'] if r.get('native_bucket')==bucket]
            if len(records)!=len(matches) or any(matches[i].get('native_card')!=record or not matches[i].get('definition') or not matches[i].get('stock_resource') for i,record in enumerate(records)):
                raise ValueError('Native predefined card consumer incomplete')
            for record,match in zip(records,matches):
                resource=predefined_profile['resources'].get(match['stock_resource'])
                if not isinstance(resource,dict) or resource.get('initial')!=record['initialCnt'] or resource.get('capacity')!=record['initialCnt']:
                    raise ValueError('Native finite card count is not bound to its actual stock resource')
        for bucket in ('characterInsts','tokenInsts'):
            records=native['predefines'].get(bucket) or []
            matches=[r for r in predefined_profile['initial_entities'] if r.get('parameters',{}).get('native_bucket')==bucket]
            rows=len(native['mapData']['map'])
            for native_index,(record,match) in enumerate(zip(records,matches)):
                expected={'row':rows-1-record['position']['row'],'col':record['position']['col']}
                if match.get('position')!=expected or match.get('facing')!=record['direction'].lower():raise ValueError('Native predefined location/direction not consumed')
                if record.get('hidden'):
                    alias=record.get('alias')
                    binding=story_bindings.get((bucket,native_index))
                    if binding is not None:
                        if (alias is not None or match.get('active') is not False
                            or match.get('registration_key')!=binding['activation_key']
                            or match.get('instanceAlias') is not None or match.get('definition')!=binding['definition']
                            or match.get('parameters',{}).get('native_story_key_binding')!=binding):
                            raise ValueError('Story-key registration must preserve hidden null alias and exact source mapping')
                    elif (not isinstance(alias,str) or not alias or match.get('active') is not False
                            or match.get('registration_key')!=alias or match.get('instanceAlias')!=alias):
                        raise ValueError('Hidden predefined requires exact alias and truly dormant registration')
                elif match.get('active',True) is not True:
                    raise ValueError('Visible predefined cannot be silently authored dormant')
    options=native['options'];mp=map_plan(native);rows=mp['rows'];controls=[];waves=[];counts=Counter()
    rune_notes=[]
    for rune in native.get('runes') or []:
        mask=MASKS.get(rune['difficultyMask']) if isinstance(rune['difficultyMask'],str) else rune['difficultyMask']
        if type(mask) is not int or mask<0 or mask>15:raise ValueError('Unknown native rune difficulty mask')
        # This is the frozen standard-mainline NORMAL1 policy; preserve NONE0
        # and FOUR_STAR2 data, rather than applying them without evidence.
        active=bool(mask&1);rune_notes.append({'raw':deepcopy(rune),'difficulty_bit':1,'active':active})
        if active:raise ValueError('Active native rune needs explicit formula/selector conversion')
    for wi,wave in enumerate(native['waves']):
        out={'pre_delay_seconds':wave['preDelay'],'post_delay_seconds':wave['postDelay'],'max_wait_seconds':wave['maxTimeWaitingForNextWave'],'fragments':[]}
        for fi,fragment in enumerate(wave['fragments']):
            frag={'pre_delay_seconds':fragment['preDelay'],'actions':[]}
            for ai,action in enumerate(fragment['actions']):
                kind=action['actionType'];meta={'native_wave':wi,'native_fragment':fi,'native_action_index':ai,'native_action':deepcopy(action)}
                common={'count':action['count'],'delay_seconds':action['preDelay'],'interval_seconds':action['interval'],
                        'managed':action['managedByScheduler'],'blocks_wave':not action['dontBlockWave'],'blocks_fragment':action['blockFragment'],'metadata':meta}
                if any(action.get(k) for k in ('hiddenGroup','randomSpawnGroupKey','randomSpawnGroupPackKey','forceBlockWaveInBranch')):
                    raise ValueError('Grouped/special native action requires explicit conversion')
                if action['randomType']!='ALWAYS' or action['refreshType']!='ALWAYS':raise ValueError('Conditional native action requires explicit conversion')
                combined=action.get('isUnharmfulAndAlwaysCountAsKilled',False)
                if type(combined) is not bool:raise ValueError('Strict combined lifecycle flag required')
                lifecycle=None;identity=(wi,fi,ai)
                if combined:
                    profile=provided.get(identity)
                    if (profile is None or profile['native_id']!=native_id or profile['native_action']!=action or kind!='SPAWN'):
                        raise ValueError('Special spawn requires exact source lifecycle profile')
                    lifecycle=profile['lifecycle']
                    if (not isinstance(lifecycle,dict) or set(lifecycle)!={'exit_rule','exit_parameters'} or not isinstance(lifecycle['exit_rule'],str) or not lifecycle['exit_rule']
                        or not isinstance(lifecycle['exit_parameters'],dict)
                        or type(lifecycle['exit_parameters'].get('unharmful')) is not bool
                        or type(lifecycle['exit_parameters'].get('always_count_as_killed')) is not bool
                        or type(lifecycle['exit_parameters'].get('loss')) is not int
                        or lifecycle['exit_parameters']!={'unharmful':True,'always_count_as_killed':True,'loss':1}):
                        raise ValueError('Combined source flag requires exact explicit exit-only policy')
                    consumed.add(identity)
                elif identity in provided:raise ValueError('Lifecycle profile does not match a special source action')

                if kind=='SPAWN':
                    if action['key'] not in bindings:raise ValueError('Unbound exact native enemy '+action['key'])
                    binding=bindings[action['key']];index=action['routeIndex']
                    if type(index) is not int or not 0<=index<len(native['routes']):raise ValueError('Native spawn route index invalid')
                    route=route_ir(native['routes'][index],rows)
                    if route['motionMode']=='E_NUM':route['motionMode']=binding['motion']
                    if route['motionMode'] not in ('WALK','FLY'):raise ValueError('Unknown native route motion')
                    if any(any((c.get('reachOffset') or {}).values()) for c in route.get('checkpoints',[])):
                        route['reach_offset_policy']={'rule':'rule/m9_checkpoint_cartesian','parameters':{'axis_signs':{'row':-1,'col':1}}}
                    if any(c['type'] in ('DISAPPEAR','APPEAR_AT_POS') for c in route.get('checkpoints',[])):
                        route['transition_policy']={'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}}
                    offset,extent=route['spawnOffset'],route['spawnRandomRange']
                    spawn={'definition':binding['unit'],'route':route,'position':deepcopy(route['startPosition']),
                        'instanceAlias':f'{native_id}/w{wi}/f{fi}/a{ai}','parameters':{'native_wave':wi,'native_fragment':fi,'native_action_index':ai,'native_route_index':index},
                        'placement':{'rule':'rule/m7_spawn_rectangle','stream':'spawn','sample_axes':['col','row'],'sample_zero_range':False,
                                     'offset':{'row':-offset['y'],'col':offset['x']},'random_range':{'row':extent['y'],'col':extent['x']}}}
                    if lifecycle is not None:spawn['components']={'lifecycle':deepcopy(lifecycle)}
                    frag['actions'].append({'kind':'spawn','spawn':spawn,**common});counts[action['key']]+=action['count']
                elif kind=='ACTIVATE_PREDEFINED':
                    key=action['key']
                    registrations=[r for r in (predefined_profile or {}).get('initial_entities',[]) if r.get('registration_key')==key and r.get('active') is False]
                    if type(key) is not str or not key or type(action['count']) is not int or action['count']!=1 or len(registrations)!=1:
                        raise ValueError('Source activation requires one actual dormant instance')
                    # The source managed activation is synchronous. Existing
                    # effects IR cannot retain membership, so release it at
                    # execution and preserve every source flag in metadata.
                    frag['actions'].append({'kind':'effects','effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':key}}],
                        **common,'managed':False,'blocks_wave':False,'blocks_fragment':False})
                elif kind=='STORY':
                    profile=(story_controls or {}).get(action['key'])
                    if not isinstance(profile,dict) or profile.get('kind')!='control':
                        raise ValueError('Native STORY requires source-bound lifecycle profile: '+action['key'])
                    if profile.get('metadata',{}).get('native_story_key')!=action['key'] or not profile.get('metadata',{}).get('native_story_source'):
                        raise ValueError('Native STORY profile lacks exact key/source binding')
                    controls.append(deepcopy(profile))
                    frag['actions'].append({'kind':'control','definition':profile['id'],**common})
                elif kind in ('DISPLAY_ENEMY_INFO','PREVIEW_CURSOR'):
                    control_id=f'control/reference/{native_id}/w{wi}f{fi}a{ai}'
                    controls.append({'id':control_id,'kind':'control','clock_policy':'logical','ack_policy':'immediate',
                        'steps':[{'kind':'effects','effects':[{'op':'emit','target':'battle','event':'reference.enemy_info.observed' if kind=='DISPLAY_ENEMY_INFO' else 'reference.route_preview.observed','payload':{**meta,'native_route':deepcopy(native['routes'][action['routeIndex']])}}]}],
                        'metadata':{**meta,'profile':'declared immediate UI-info/route-preview observation with managed membership; no rendering claim'}})
                    frag['actions'].append({'kind':'control','definition':control_id,**common})
                else:raise ValueError('Unconverted native action '+str(kind))
            out['fragments'].append(frag)
        waves.append(out)
    if set(provided)!=consumed:raise ValueError('Unused source lifecycle profile')
    map_definition={k:deepcopy(mp[k]) for k in ('rows','cols','tiles')};map_definition['tile_mechanics']=deepcopy(tile_profiles)
    required={t['tileKey'] for t in mp['tiles'] if t['tileKey'] not in {'tile_floor','tile_road','tile_wall','tile_forbidden','tile_start','tile_end','tile_empty','tile_flystart'}}
    if not required<=set(tile_profiles):raise ValueError('Required map mechanics lack profiles: '+','.join(sorted(required-set(tile_profiles))))
    scenario={'id':'scene/reference/'+native_id,'ruleset':'ruleset/ark_standard','seed':native['randomSeed'] if seed is None else seed,
        'map':map_definition,'resources':{'dp':{'initial':options['initialCost'],'capacity':options['maxCost'],'recovery_rate':1/options['costIncreaseTime'],
            'recovery':{'mode':'periodic','interval_seconds':options['costIncreaseTime']}},'life':{'initial':options['maxLifePoint'],'capacity':options['maxLifePoint']}},
        'parameters':{'deploy_capacity':options['characterLimit']},'objectives':{'type':'waves','life_resource':'life'},
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':waves},
        'metadata':{'native_id':native_id,'native_options':deepcopy(options),'rune_policy':rune_notes,'native_spawn_counts':dict(counts),
                    'coordinate_policy':mp['coordinate_conversion'],'client_feedback_pending':True,
                    'activation_policy':'Source managed activation releases synchronously; raw flags preserved in action metadata',
                    'source_lifecycle_profiles':deepcopy(profiles)}}
    if has_predefines:
        extra=deepcopy(predefined_profile['resources'])
        if set(extra)&set(scenario['resources']):raise ValueError('Predefined resources cannot replace native DP/life')
        scenario['resources'].update(extra);scenario['initialEntities']=deepcopy(predefined_profile['initial_entities'])
        scenario['metadata']['native_card_bindings']=deepcopy(predefined_profile['card_bindings'])
        scenario['metadata']['native_predefines']=deepcopy(native['predefines'])
    return scenario,controls
