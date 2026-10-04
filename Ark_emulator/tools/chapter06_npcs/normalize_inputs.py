"""Normalize exact native NPC configs without a fixed-roster or skill[-1] path."""
from copy import deepcopy
from fractions import Fraction
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.normalize_campaign_operators import interpolate,half_away_integer,rational_json,ROUNDING_PROFILE,phase_number
SOURCE=ROOT/'packages/campaign/chapter06_predefines/source.reference.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def normalized(record):
    raw=record['raw_native'];inst=raw['inst'];character=record['raw_character']
    if type(raw['skillIndex']) is not int or raw['skillIndex']!=-1:
        raise ValueError('This exact native no-skill NPC profile requires integer -1')
    phase=phase_number(inst['phase']);level=inst['level']
    if phase>=len(character['phases']):raise ValueError('Native NPC phase unavailable')
    if type(level) is not int or not 1<=level<=character['phases'][phase]['maxLevel']:
        raise ValueError('Native NPC level invalid')
    if type(inst['favorPoint']) is not int or type(inst['potentialRank']) is not int or inst['favorPoint']!=0 or inst['potentialRank']!=0:
        raise ValueError('Exact C6 NPC profile uses zero favor/potential rank')
    base,growth=interpolate(character['phases'][phase]['attributesKeyFrames'],level)
    favor,favor_inputs=interpolate(character['favorKeyFrames'],0)
    if set(base)!=set(favor):raise ValueError('NPC base/favor field sets differ')
    values={};provenance={}
    for key,value in base.items():
        bonus=favor[key]
        if type(value) is bool:
            if bonus is not False:raise ValueError('Changing favor Boolean unsupported')
            values[key]=value;provenance[key]={'source_boolean':value};continue
        total=value+bonus
        selected=half_away_integer(total) if key in ROUNDING_PROFILE['integer_attributes'] else float(total)
        values[key]=selected;provenance[key]={'base':rational_json(value),'favor':rational_json(bonus),'unrounded':rational_json(total),'model':selected}
    talents=[]
    for index,tree in enumerate(character.get('talents') or []):
        eligible=[candidate for candidate in tree['candidates']
                  if (phase_number(candidate['unlockCondition']['phase']),candidate['unlockCondition']['level'])<=(phase,level)
                  and candidate['requiredPotentialRank']<=inst['potentialRank']]
        if not eligible:continue
        selected=max(eligible,key=lambda row:(phase_number(row['unlockCondition']['phase']),row['unlockCondition']['level'],row['requiredPotentialRank']))
        talents.append({'slot':index,'candidate':deepcopy(selected)})
    return {'character_id':inst['characterKey'],'native_instance':deepcopy(raw),'phase':phase,'level':level,
            'favor_point':0,'potential_rank':0,'selected_skill':None,'skill_index':-1,'stats':values,'stat_inputs':provenance,
            'growth':growth,'favor_inputs':favor_inputs,'range_id':character['phases'][phase]['rangeId'],'selected_talents':talents,
            'rounding_policy':deepcopy(ROUNDING_PROFILE),'runtime_authored':False}


def build():
    source=json.loads(SOURCE.read_bytes());rows=[]
    for record in source['stages']['level_main_06-15']['instances']:
        row=normalized(record);key=row['character_id'];prefab=source['prefabs'][key]
        root=next(c for c in prefab['components'].values() if c['native_class']=='Character')
        mode=prefab['components'][str(root['raw']['_modes'][0]['m_PathID'])]
        attack=prefab['components'][str(mode['raw']['_attack']['m_PathID'])]
        binding=source['animations'][key]['modes'][0]
        assert binding['mode_path_id']==root['raw']['_modes'][0]['m_PathID'] and binding['attack_path_id']==mode['raw']['_attack']['m_PathID']
        front,back=binding['bindings_by_face']['front'],binding['bindings_by_face']['back']
        assert front['events']==back['events'] and front.get('begin_animation',{}).get('duration')==back.get('begin_animation',{}).get('duration')
        row.update(normal_mode_source=deepcopy(mode),normal_attack_source=deepcopy(attack),normal_animation=deepcopy(binding),
            exact_root_source=deepcopy(root),prefab_source=deepcopy(prefab['source']))
        row['required_consumers']=['Default-mode ordinary attack and exact projectile payload','Native trait/selected talents','External story-key hidden activation']
        if key=='char_002_amiya':row['required_consumers']+=['Three-part begin19-event vs mode timing, MultiRanged additional placeholder payloads','Attack/kill SP talent with no selected skill']
        if key=='char_017_huang':row['required_consumers']+=['Multi-block target count trait','Once-only HP threshold heal/minHP lock','15s status-resistance passive']
        if key=='char_367_swllow':row['required_consumers']+=['ASPD additive6','Dice15% conditional physical scale1.5 and real projectile']
        rows.append(row)
    assert len(rows)==3
    return {'schema':'ark-sim/ch6-native-npc-inputs/v1','source_sha':sha(SOURCE),'source_locks':deepcopy(source['source_locks']),
        'records':rows,'scope':'Exact E2L25/no-favor/no-skill native input normalization. Base interpolation/rounding are explicit reference policy; runtime consumers pending.',
        'whole_stage_executed':False,'client_verified':False,'builder_sha':sha(Path(__file__))}


def main():
    out=ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json';assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True)
    before=sha(SOURCE);value=build();assert sha(SOURCE)==before
    out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(out),'npc_stats':[{'character':r['character_id'],'hp':r['stats']['maxHp'],'atk':r['stats']['atk'],'def':r['stats']['def'],'talents':len(r['selected_talents'])} for r in value['records']]}))


if __name__=='__main__':main()
