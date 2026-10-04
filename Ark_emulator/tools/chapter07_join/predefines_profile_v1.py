"""Exact native instance/card input mapping; fixed squad remains separate."""
from copy import deepcopy
from tools.chapter06_review.stage_converter_v7 import exact

ORE='unit/ch7/predefined/ore/level1'
MINE='unit/ch7/predefined/mine/level1'


def profile(native,source_native):
    if not exact(native['predefines'],source_native):
        raise ValueError('Native predefined source types/values differ')
    result={'native_predefines':deepcopy(source_native),'initial_entities':[],'card_bindings':[],'resources':{}}
    rows=len(native['mapData']['map'])
    for bucket in ('characterInsts','tokenInsts'):
        for raw in source_native.get(bucket) or []:
            if not exact(raw['inst'],{'characterKey':'trap_011_ore','level':1,'phase':'PHASE_0','favorPoint':0,'potentialRank':0}):
                raise ValueError('Unconsumed native instance configuration')
            if raw['hidden'] is not False or type(raw['skillIndex']) is not int or raw['skillIndex']!=0 or type(raw['mainSkillLvl']) is not int or raw['mainSkillLvl']!=1:
                raise ValueError('Unconsumed ore visibility/skill configuration')
            if raw.get('overrideSkillBlackboard') or raw.get('overrideTalents') or raw.get('uniEquipIds'):
                raise ValueError('Unconsumed ore runtime override')
            item={'definition':ORE,'position':{'row':rows-1-raw['position']['row'],'col':raw['position']['col']},
                  'facing':raw['direction'].lower(),'parameters':{'native_bucket':bucket,'native_instance':deepcopy(raw)}}
            if raw['alias'] is not None:item['instanceAlias']=raw['alias']
            result['initial_entities'].append(item)
    for bucket in ('characterCards','tokenCards'):
        for raw in source_native.get(bucket) or []:
            if not exact(raw['inst'],{'characterKey':'trap_012_mine','level':1,'phase':'PHASE_0','favorPoint':0,'potentialRank':0}):
                raise ValueError('Unconsumed native card configuration')
            if (raw['hidden'] is not False or type(raw['skillIndex']) is not int or raw['skillIndex']!=0 or type(raw['mainSkillLvl']) is not int or raw['mainSkillLvl']!=1
                or type(raw['initialCnt']) is not int or raw['initialCnt']<=0):
                raise ValueError('Explicit native card visibility/skill/finite stock required')
            if raw.get('overrideSkillBlackboard') or raw.get('overrideTalents') or raw.get('uniEquipIds'):
                raise ValueError('Unconsumed native card runtime override')
            resource='stock_ch7_mine'
            if resource in result['resources']:raise ValueError('Repeated native card stock not implicitly merged')
            result['resources'][resource]={'initial':raw['initialCnt'],'capacity':raw['initialCnt']}
            result['card_bindings'].append({'native_bucket':bucket,'native_card':deepcopy(raw),
                                            'definition':MINE,'stock_resource':resource})
    return result


def declared_cards(profile):
    return [card['definition'] for card in profile['card_bindings']]
