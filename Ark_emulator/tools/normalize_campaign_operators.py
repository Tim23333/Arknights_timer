"""Offline canonical campaign operator inputs from immutable standard tables.

Produces source-backed frames and an explicitly unverified model stat profile.
It does not import a simulator or execute skills/talents. --check refuses any
source/cache/config/output drift; --fetch is the explicit cache acquisition.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from fractions import Fraction

ROOT=Path(__file__).resolve().parents[1]
COMMIT='56aee3d6c5a29c3a0d192456d70d14252cbb0804'
CACHE=ROOT.parent/'unpack_work/campaign_tables'
LOCK=ROOT/'packages/campaign/operator_sources.lock.json'
OUTPUT=ROOT/'packages/campaign/operators.normalized.json'
TABLES=('character_table.json','skill_table.json')
ROUNDING_PROFILE={
    'id':'campaign.linear_frames.favor_endpoint100.half_up.v1',
    'interpolation':'piecewise linear, exact rational from decimal JSON numbers',
    'trust_mapping':'trust_percent / 2, capped at favor frame level50; 100 percent maps to50',
    'integer_attributes':['maxHp','atk','def','cost','blockCnt','respawnTime','maxDeployCount',
                          'maxDeckStackCnt','tauntLevel','massLevel','baseForceLevel'],
    'rounding':'add unrounded base + favor; nearest integer with half away from zero for integer attributes',
    'other_numeric_attributes':'preserve exact rational and expose a model decimal value',
    'talents_applied_to_stats':False,'potential_applied_to_stats':False,
    'equipment_applied_to_stats':False,'client_formula_verified':False,
    'calibration':'source endpoints are exact; intermediate rounding and UI trust mapping are explicit model assumptions pending client/formula calibration',
}


class NormalizationError(ValueError):
    pass


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    if not Path(path).is_file():
        raise FileNotFoundError(f'Required campaign normalization source missing: {path}')
    return json.loads(Path(path).read_text(encoding='utf8'))


def source_url(name):
    if name not in TABLES:
        raise NormalizationError(f'Unsupported standard table {name!r}')
    return f'https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/{COMMIT}/cn/gamedata/excel/{name}'


def source_entry(name,path):
    data=path.read_bytes()
    value=json.loads(data.decode('utf8'))
    if not isinstance(value,dict) or not value:
        raise NormalizationError(f'{name}: standard table must be a nonempty object')
    url=source_url(name);checksum=sha_bytes(data)
    return {'url':url,'commit':COMMIT,'path':Path(os.path.relpath(path,ROOT)).as_posix(),
            'sha256':checksum,'size':len(data),'cache_identity':sha_bytes((url+'\n'+checksum).encode())}


def fetch_sources(refresh=False):
    CACHE.mkdir(parents=True,exist_ok=True)
    existing=read_json(LOCK) if LOCK.exists() else None
    entries={}
    for name in TABLES:
        path=CACHE/name
        if path.exists() and existing and not refresh:
            actual=source_entry(name,path)
            if existing.get('files',{}).get(name)!=actual:
                raise NormalizationError(f'{name}: locked cache checksum/identity mismatch; explicit --refresh required')
            entries[name]=actual
            continue
        descriptor,tmpname=tempfile.mkstemp(prefix='.'+name+'.',suffix='.download',dir=CACHE)
        os.close(descriptor);temporary=Path(tmpname)
        try:
            result=subprocess.run(['curl.exe','--fail','--location','--silent','--show-error',
                '--proto','=https','--proto-redir','=https','--tlsv1.2','--connect-timeout','15',
                '--max-time','90','--output',str(temporary),source_url(name)],capture_output=True,text=True,timeout=95)
            if result.returncode:
                raise NormalizationError(f'{name}: curl failed: {result.stderr[:400]}')
            # Validate table before touching the destination.
            value=read_json(temporary)
            if not isinstance(value,dict) or not value:
                raise NormalizationError(f'{name}: invalid downloaded standard table')
            if path.exists() and not refresh and path.read_bytes()!=temporary.read_bytes():
                raise NormalizationError(f'{name}: unlocked cache differs from fixed download; explicit --refresh required')
            os.replace(temporary,path)
            entries[name]=source_entry(name,path)
        finally:
            temporary.unlink(missing_ok=True)
    lock={'schema':'ark_sim.campaign_operator_sources.v1','repository':'ArknightsAssets/ArknightsGamedata',
          'commit':COMMIT,'files':entries}
    LOCK.write_text(json.dumps(lock,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    return lock


def load_sources():
    lock=read_json(LOCK)
    if lock.get('schema')!='ark_sim.campaign_operator_sources.v1' or lock.get('commit')!=COMMIT or lock.get('repository')!='ArknightsAssets/ArknightsGamedata':
        raise NormalizationError('Operator source lock identity mismatch')
    if set(lock.get('files',{}))!=set(TABLES):
        raise NormalizationError('Operator source lock table set mismatch')
    for name in TABLES:
        if source_entry(name,CACHE/name)!=lock['files'][name]:
            raise NormalizationError(f'{name}: source checksum/identity mismatch')
    return read_json(CACHE/TABLES[0]),read_json(CACHE/TABLES[1]),lock


def phase_number(value):
    if isinstance(value,int) and not isinstance(value,bool) and 0<=value<=2:
        return value
    if isinstance(value,str) and re.fullmatch('PHASE_[012]',value):
        return int(value[-1])
    raise NormalizationError(f'Invalid elite phase {value!r}')


def unlocked(condition,config):
    if not isinstance(condition,dict) or 'phase' not in condition or 'level' not in condition:
        raise NormalizationError('Unlock condition missing phase/level')
    return (config['elite_phase'],config['level'])>=(phase_number(condition['phase']),condition['level'])


def fraction(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise NormalizationError(f'Invalid numerical stat input {value!r}')
    return Fraction(str(value))


def interpolate(frames,level):
    if not isinstance(frames,list) or not frames:
        raise NormalizationError('Missing attribute/trust key frames')
    if isinstance(level,bool) or not isinstance(level,(int,Fraction)):
        raise NormalizationError('Interpolation level must be integer or exact rational')
    positions=[f['level'] for f in frames]
    if positions!=sorted(set(positions)):
        raise NormalizationError('Key frame levels must strictly increase')
    if not positions[0]<=level<=positions[-1]:
        raise NormalizationError('Interpolation level outside source key frames')
    if len(frames)==1:
        lo=hi=frames[0];alpha=Fraction(0)
    else:
        lo,hi=next((a,b) for a,b in zip(frames,frames[1:]) if a['level']<=level<=b['level'])
        alpha=Fraction(level-lo['level'])/(hi['level']-lo['level'])
    if set(lo['data'])!=set(hi['data']):
        raise NormalizationError('Attribute key frame field sets differ')
    out={}
    for k,a in lo['data'].items():
        b=hi['data'][k]
        if isinstance(a,bool) or isinstance(b,bool):
            if not isinstance(a,bool) or not isinstance(b,bool) or a!=b:
                raise NormalizationError(f'Cannot interpolate changing boolean stat {k}')
            out[k]=a
        else:
            out[k]=fraction(a)+(fraction(b)-fraction(a))*alpha
    return out,{'lower_level':lo['level'],'upper_level':hi['level'],
                'alpha_numerator':alpha.numerator,'alpha_denominator':alpha.denominator}


def half_away_integer(value):
    sign=-1 if value<0 else 1
    value=abs(value)
    return sign*((2*value.numerator+value.denominator)//(2*value.denominator))


def rational_json(value):
    return {'numerator':value.numerator,'denominator':value.denominator}


def validate_config(character,config):
    if 'equipment_id' not in config:
        raise NormalizationError('Configuration equipment_id must be explicit, including null')
    for k in ('elite_phase','level','potential','potential_rank','trust_percent','mastery','skill_rank','skill_level_index'):
        if k not in config or isinstance(config[k],bool) or not isinstance(config[k],int):
            raise NormalizationError(f'Configuration {k} must be an explicit integer')
    phase=phase_number(config['elite_phase'])
    if phase>=len(character.get('phases') or []):
        raise NormalizationError('Configured elite phase unavailable')
    if not 1<=config['level']<=character['phases'][phase]['maxLevel']:
        raise NormalizationError('Configured level outside phase maximum')
    if config['potential']!=1 or config['potential_rank']!=0:
        raise NormalizationError('This no-potential-bonus campaign profile requires potential1/rank0')
    if not 0<=config['trust_percent']<=200:
        raise NormalizationError('Trust percent outside 0..200')
    if config.get('equipment_id') is not None or config.get('equipment_level')!=0:
        raise NormalizationError('Campaign profile requires no equipment/module')
    if config['skill_rank']!=7 or config['mastery']!=3 or config['skill_level_index']!=9:
        raise NormalizationError('Selected campaign skill must be rank7/mastery3/native index9')


def compute_stats(character,config):
    validate_config(character,config)
    phase=character['phases'][config['elite_phase']]
    base,base_inputs=interpolate(phase['attributesKeyFrames'],config['level'])
    favor=character.get('favorKeyFrames')
    if favor is None:
        raise NormalizationError('favorKeyFrames missing; refusing zero-trust fallback')
    if not favor or favor[0]['level']!=0 or favor[-1]['level']!=50:
        raise NormalizationError('This trust model requires native favor endpoints0 and50')
    trust_level=min(Fraction(config['trust_percent'],2),Fraction(50))
    trust,trust_inputs=interpolate(favor,trust_level)
    if set(base)!=set(trust):
        raise NormalizationError('Base and favor attribute field sets differ')
    stats={};components={}
    for k,value in base.items():
        delta=trust[k]
        if isinstance(value,bool):
            if delta is not False:
                raise NormalizationError(f'Unsupported trust boolean bonus {k}')
            stats[k]=value;components[k]={'base':value,'favor':False,'model':value}
            continue
        if isinstance(delta,bool):
            raise NormalizationError(f'Incompatible trust stat type {k}')
        total=value+delta
        model=half_away_integer(total) if k in ROUNDING_PROFILE['integer_attributes'] else float(total)
        stats[k]=model
        components[k]={'base':rational_json(value),'favor':rational_json(delta),'unrounded_total':rational_json(total),'model':model}
    return {'model_stats':stats,'components':components,'growth_inputs':base_inputs,'trust_inputs':trust_inputs,
            'trust_native_level':rational_json(trust_level),'client_formula_verified':False}


def eligible_candidates(container,config):
    if container is None:
        return []
    if not isinstance(container,dict) or not isinstance(container.get('candidates'),list):
        raise NormalizationError('Trait/talent candidates missing')
    return [c for c in container['candidates'] if unlocked(c['unlockCondition'],config)
            and c['requiredPotentialRank']<=config['potential_rank']]


def normalize_operator(row,character,skills):
    for name in ('name','description','profession','subProfessionId','phases','favorKeyFrames','skills','talents','trait','allSkillLvlup'):
        if name not in character:
            raise NormalizationError(f'Required standard character field absent: {name}')
    config=row['config'];validate_config(character,config)
    if (config['elite_phase'],config['level'],config['trust_percent'])!=(2,70,100):
        raise NormalizationError('Frozen roster normalization requires E2 level70 trust100')
    wanted=config['skill_id']
    matches=[(i,s) for i,s in enumerate(character['skills']) if s['skillId']==wanted]
    if len(matches)!=1:
        raise NormalizationError(f'{row["character_id"]}: selected skill ID not uniquely present in standard character table')
    skill_index,slot=matches[0]
    if not unlocked(slot['unlockCond'],config):
        raise NormalizationError('Selected skill is locked')
    rank_conditions=character.get('allSkillLvlup')
    if not isinstance(rank_conditions,list) or len(rank_conditions)<6 or not all(unlocked(c['unlockCond'],config) for c in rank_conditions[:6]):
        raise NormalizationError('Selected skill rank7 is locked or missing')
    if len(slot.get('levelUpCostCond') or [])<3 or not all(unlocked(c['unlockCond'],config) for c in slot['levelUpCostCond'][:3]):
        raise NormalizationError('Selected mastery3 is locked or missing')
    if wanted not in skills or len(skills[wanted].get('levels') or [])<=config['skill_level_index']:
        raise NormalizationError('Selected native skill level index missing')
    skill=skills[wanted]['levels'][config['skill_level_index']]
    for k in ('spData','skillType','durationType','duration','blackboard','prefabId'):
        if k not in skill or (k!='blackboard' and skill[k] is None):
            raise NormalizationError(f'Selected skill field missing: {k}')
    for k in ('spType','spCost','initSp','increment','maxChargeTime'):
        if k not in skill['spData'] or skill['spData'][k] is None:
            raise NormalizationError(f'Selected skill SP field missing: {k}')
    talents=[]
    for i,talent in enumerate(character.get('talents') or []):
        available=eligible_candidates(talent,config)
        chosen=max(available,key=lambda c:(phase_number(c['unlockCondition']['phase']),c['unlockCondition']['level'],c['requiredPotentialRank'])) if available else None
        talents.append({'slot_index':i,'unlocked_candidates':available,'selected_candidate':chosen})
    phase=character['phases'][config['elite_phase']]
    trait_candidates=eligible_candidates(character.get('trait'),config)
    selected_trait=max(trait_candidates,key=lambda c:(phase_number(c['unlockCondition']['phase']),c['unlockCondition']['level'],c['requiredPotentialRank'])) if trait_candidates else None
    range_id=phase.get('rangeId')
    gaps=['range_coordinates_not_in_character_or_skill_table','normal_attack_animation_and_effect_frames_missing',
          'normal_attack_projectile_and_damage_semantics_missing','talent_and_trait_native_prefab_components_missing',
          'client_stat_rounding_and_trust_mapping_pending']
    if range_id is None:
        gaps.append('normal_attack_range_id_missing')
    if phase.get('characterPrefabKey') is None:
        gaps.append('normal_attack_character_prefab_key_missing')
    return {'order':row['order'],'character_id':row['character_id'],'name':character['name'],'config':config,
            'status':'source_normalized_model_profile_unvalidated','runnable':False,'model_validated':False,'client_validated':False,
            'normal_attack_source':{'range_id':range_id,'character_prefab_key':phase.get('characterPrefabKey'),
                                    'description':character.get('description'),'profession':character.get('profession'),
                                    'sub_profession_id':character.get('subProfessionId')},
            'stats':compute_stats(character,config),'phase_key_frames':phase['attributesKeyFrames'],
            'favor_key_frames':character['favorKeyFrames'],'talents':talents,'trait_raw':character.get('trait'),
            'unlocked_trait_candidates':trait_candidates,'selected_trait_candidate':selected_trait,
            'selected_skill':{'character_skill_index':skill_index,
                'skill_id':wanted,'native_level_index':9,'character_skill_slot':slot,'level':skill},
            'gaps':gaps,'raw_character':character,'raw_selected_skill':skills[wanted]}


def build():
    characters,skills,lock=load_sources()
    roster_path=ROOT/'packages/campaign/roster.reference.json'
    roster=read_json(roster_path)
    if len(roster['roster'])!=12:
        raise NormalizationError('Expected fixed twelve-person roster')
    if len({r['character_id'] for r in roster['roster']})!=12 or sorted(r['order'] for r in roster['roster'])!=list(range(1,13)):
        raise NormalizationError('Frozen roster requires unique characters and contiguous order1..12')
    operators=[]
    for row in sorted(roster['roster'],key=lambda r:r['order']):
        cid=row['character_id']
        if cid not in characters:
            raise NormalizationError(f'Required operator missing in fixed standard table: {cid}')
        operators.append(normalize_operator(row,characters[cid],skills))
    dependent_ids=sorted(set(roster['token_ids']+roster['trait_character_ids']))
    dependencies={}
    for cid in dependent_ids:
        if cid not in characters:
            raise NormalizationError(f'Required token/trait reference missing: {cid}')
        raw=characters[cid]
        deps={}
        null_slots=[]
        for i,slot in enumerate(raw.get('skills') or []):
            sid=slot['skillId']
            if sid is None:
                null_slots.append(i)
                continue
            if sid not in skills:
                raise NormalizationError(f'Dependent character skill missing: {cid}/{sid}')
            deps[sid]=skills[sid]
        dependencies[cid]={'raw_character':raw,'raw_skills':deps,
            'null_skill_id_slots':null_slots,'null_skill_ids_are_not_synthesized':True,
            'status':'source_only_owner_growth_and_trust_inheritance_pending',
            'token':cid in roster['token_ids'],'trait_reference':cid in roster['trait_character_ids']}
    linked_skill_ids=sorted(sid for sid in roster['frozen']['skills'] if sid.startswith('sktok_'))
    linked_skills={}
    for sid in linked_skill_ids:
        if sid not in skills:
            raise NormalizationError(f'Frozen token skill reference absent in standard table: {sid}')
        linked_skills[sid]={'raw_skill':skills[sid],'association_source':'roster.reference.frozen.skills',
                            'runtime_token_binding_status':'pending'}
    subset={'operators':operators,'dependent_characters':dependencies,'linked_token_skills':linked_skills}
    return {'schema':'ark_sim.campaign_operators_normalized.v1','offline_only':True,
            'status':'source_normalized_model_profile_unvalidated','runnable':False,
            'source_lock':lock,'roster_source':{'path':'packages/campaign/roster.reference.json',
                'sha256':sha_bytes(roster_path.read_bytes()),'frozen_sha256':roster['frozen_sha256']},
            'normalizer_source_sha256':sha_bytes(Path(__file__).read_bytes()),
            'rounding_profile':ROUNDING_PROFILE,'subset_sha256':sha_bytes(canonical(subset)),**subset}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch',action='store_true')
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.refresh and not args.fetch:
        parser.error('--refresh requires explicit --fetch')
    if args.check and args.fetch:
        parser.error('--check cannot acquire or replace source data')
    if args.fetch:
        fetch_sources(args.refresh)
    result=build()
    if args.check:
        if read_json(OUTPUT)!=result:
            raise NormalizationError('Normalized operator output differs from source/config/profile rebuild')
        print('Operator normalization identity/content check passed')
    else:
        OUTPUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf8')
        print(f'Normalized {len(result["operators"])} operators and {len(result["dependent_characters"])} source dependencies')


if __name__=='__main__':
    main()
