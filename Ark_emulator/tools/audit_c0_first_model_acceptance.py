"""Read-only typed c0/M10 acceptance inventory; never promotes historical evidence."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


SOURCES={'char_003_kalts':('kalts','support'),'char_010_chen':('chen','attack'),'char_103_angel':('angel','attack'),
    'char_107_liskam':('liskam','attack'),'char_128_plosis':('plosis','support'),'char_151_myrtle':('myrtle','attack'),
    'char_179_cgbird':('cgbird','support'),'char_180_amgoat':('amgoat','attack'),'char_202_demkni':('demkni','support'),
    'char_222_bpipe':('bpipe','attack'),'char_358_lisa':('lisa','support'),'char_400_weedy':('weedy','support')}


MECHANICS={
 'char_010_chen':['attack event once/normal twohit13,30','AUTO S1cost4/3.2physical/stun1.5','4s attack-damage SP/ATKDEF5%/physicaldodge10','exact selected S1 freeze with normal SP preserved'],
 'char_151_myrtle':['S2 payment24/duration16/16DP','single injured .5ATK heal16+30n','stop attack/block synchronous transition','vanguard25HP/s live aura'],
 'char_222_bpipe':['S3 payment40/20s/triple14,17,20','interval scaler+.7/ATKDEF+120%/block+1','25%critical/splash/DPkill1','deck initialSP6/withdraw raw-cost capped refund'],
 'char_103_angel':['AUTO full30 payment/15s/5shots','attack_speed+.12/1.1scale/dynamic repeat','self and random eligible friend ATK6%/HP10%','capacity birth/change/retire/expiry mode'],
 'char_107_liskam':['defense1+talent self1 per positive hit','neighbor random1/cardinal/empty/dead/freeze','AUTO18/shield1/DEF100%8s','RES10 and after expiry recovery'],
 'char_128_plosis':['TIME100/init85/S2 mode40s','three injured each hit/flat.75 interval profile','global highest+.3TIME SP/live membership','normal restore/source retire'],
 'char_180_amgoat':['manual80/15s/ATK130%/interval flat-1.1','automatic .5 model RNG count/dynamic6targets','caster14%ATK/live aura','on deploy float random7..16SP'],
 'char_202_demkni':['manual80/30s/live enemy aura slow/arts1.55','all injured .35ATK heal each1s','20s×5 ATK5% DEF4% staircase','accepted own healing target SP1/emission freeze'],
 'char_003_kalts':['owned DP10/capacity/cool25/source retire','self/own/foreign heal preference64 model','SP15/20s/exact S3 interruption/normal preserved','Mon f7/f20/decay/DEF/kill penalty/death1200stun3'],
 'char_358_lisa':['TIME70/init50/35s/noattack/regen .2','profession_SUPPORT highest+.4 SP','sluggish passive1.2/S3highest1.4 source bound','live enter/leave/retire/halfopen'],
 'char_179_cgbird':['TIME120/init115/60s/3target AttackC27','base RES15/S3RES150/ATK80/artsdodge25','bird cards2/DP5/capacity0/taunt1/healfree','3%HP/drop/death/source retire/cool20'],
 'char_400_weedy':['TIME33/arts3.5/AoE1.2/wait projectile','push mass+bonus profile/actual ledger1200/EXTEND/tail','owned cannon DP5/capacity0/lifetime20/cool35','normal f1/travel/SP3s/manhattan4/empty profile']}


def evidence(path,current_impl,current_input):
    value=read(path)
    impl=value.get('implementation_sha256',value.get('implementation_digest',value.get('implementation_digest_at_completion')))
    input_sha=value.get('input_package_sha256',value.get('package_sha256'))
    tests=value.get('tests',[])
    tests_current=all((ROOT/t['path']).exists() and sha(ROOT/t['path'])==t.get('source_sha256') for t in tests) if tests else None
    return {'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'passed':value.get('passed'),
        'implementation':impl,'input':input_sha,'implementation_matches_current':impl==current_impl,
        'input_matches_current':input_sha==current_input,'test_sources_match_current':tests_current,
        'current_input_mechanism_pass':value.get('passed') is True and impl==current_impl and input_sha==current_input and tests_current is True,
        'selected_cases':value.get('selected_cases',[c['case'] for c in value.get('cases',[])]),
        'state':{k:value.get('state',{}).get(k) for k in ('kills','leaks','finished','result')},
        'checkpoint_resume_equal':value.get('checkpoint_resume_equal'),'replay_equal':value.get('replay_equal'),
        'not_promoted_by_this_audit':True}


def audit():
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    source=ROOT/'packages/campaign/mainline_models/level_main_00-10.m10.json'
    stage=read(source);program=Compiler().compile(stage)
    sim=Engine.create(program) # Identity reconstruction only, zero ticks; no stage win claim.
    impl=implementation_digest();input_sha=sha(source)
    normalized={r['character_id']:r for r in read(ROOT/'packages/campaign/operators.normalized.json')['operators']}
    defs={x['id']:x for k in ('entities','abilities','buffs','selectors','rules') for x in stage[k]}
    command_path=ROOT/'validation/campaign/m10_00_10_full_20261002.commands.json'
    commands=read(command_path)
    deployed={defs[c['entity']]['metadata']['native_id'] for c in commands if c['action']=='deploy'}
    rows=[]
    for cid,(skill_source,talents) in SOURCES.items():
        unit=next(e for e in stage['entities'] if e.get('metadata',{}).get('native_id')==cid)
        row=normalized[cid];metadata=unit['metadata'];selected=defs[metadata['selected_skill_ability']]
        stat_checks={k:unit['components']['attributes']['base'][v]==row['stats']['model_stats'][k] for k,v in [('maxHp','max_hp'),('atk','atk'),('def','def'),('magicResistance','mres')]}
        paths=[ROOT/f'packages/campaign/skills.{skill_source}.json',ROOT/f'packages/campaign/talents.{talents}.json']
        rows.append({'native_id':cid,'unit_id':unit['id'],'config':metadata['config'],'config_matches_source':metadata['config']==row['config'],
            'stats_checks':stat_checks,'selected_native_id':selected.get('metadata',{}).get('native_skill_id'),
            'selected_native_matches':selected.get('metadata',{}).get('native_skill_id')==row['selected_skill']['skill_id'],
            'selected_owned':selected['id'] in unit['components']['abilities'],'selected_ability':selected['id'],
            'abilities':unit['components']['abilities'],'initial_buffs':unit['components'].get('buffs',{}).get('initial',[]),
            'talent_source_slots':len(row['talents']),'source_packages':{p.relative_to(ROOT).as_posix():sha(p) for p in paths},
            'required_math_witnesses':MECHANICS[cid],'deployed_in_saved_stage_script':cid in deployed,
            'current_status':'model_gap' if cid=='char_151_myrtle' else 'witness_missing_current_c0_identity',
            'native_full_operator_claim':False})
    names=['canonical_trio_witness.m8_roster.json','canonical_lisk_defense.m8_roster.json','canonical_night_witness.m8_targeting_v2.json',
        'canonical_weedy_witness.m8_roster.json','canonical_kalts_witness.m10_f6bb.json','m10_resource_precision_independent_review.json',
        'm10_combined_resource_independent_review.json','m10_primary_targeted_20261002.json','m10_00_10_full_20261002.json',
        'm8_damage_00_10_full_20261002.json']
    reports=[evidence(ROOT/'validation/campaign'/n,impl,input_sha) for n in names if (ROOT/'validation/campaign'/n).exists()]
    from tools.campaign_progress import execution_gate
    reference=read(ROOT/'packages/campaign/roster.reference.json')
    try:execution_gate(program,{'level_id':'level_main_00-10'},reference);gate_error=None
    except Exception as error:gate_error=str(error)
    myrtle=defs['ability/campaign_myrtle_s2'];no_block=defs['buff/campaign_myrtle_no_block']
    return {'schema':'ark-sim/c0-first-model-typed-audit/v1','scope_targets':36,'fixed_roster_count':12,'formal_approval':False,
        'implementation_sha256':impl,'input_package':source.relative_to(ROOT).as_posix(),'input_package_sha256':input_sha,
        'program_fingerprint':program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,'reconstruction_ticks':0,
        'source_chain':{p.relative_to(ROOT).as_posix():sha(p) for p in [source,ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/roster.reference.json',ROOT/'tools/build_m10_integrated_content.py',ROOT/'tools/campaign_progress.py']},
        'roster':rows,'deployed':sorted(deployed),'undeployed':sorted(set(SOURCES)-deployed),'evidence':reports,
        'typed_gaps':[{'id':'myrtle_sync_stop_block','type':'model_gap','source':'BLOCK_CNT final scaler0 active skill buff',
                'actual':'t0 new blocking; enemy cast1 before release; t19 damage9.5; held on_start/control still stale',
                'evidence':'validation/campaign/c0_myrtle_block_boundary.json'},
            {'id':'corner_projection','type':'model_gap','source':'current horizontal native grid range and continuous positions',
                'actual':'row4.5 is collision cell5 but selector cell4 and attacked; row5.5 maps6 in both',
                'evidence':'validation/campaign/c0_corner_projection.json','next_independent_candidate':'M12; not merged into frozen M11'},
            {'id':'current_stage_three_way','type':'witness_missing','detail':'M10/c0 same package+script full victory/conservation/CP/replay artifact required; live false is not failure verdict'},
            {'id':'current_canonical_all12','type':'witness_missing','detail':'old f8/f6bb positives are historical; fresh c0 test inventory must explicitly bind current input/environment and six deployed skills/talents'},
            {'id':'native_callbacks_clock_version','type':'client_pending','detail':'explicit complete math profiles retain native comparator/FSM/RNG/frame/source-version pending; no blanket promotion'},
            {'id':'execution_contract','type':'gate_contract_gap','detail':gate_error},
            {'id':'independent_receipt','type':'gate_contract_gap','detail':'no current complete source/config/input/runtime review receipt issued by this audit'}],
        'myrtle_binding':{'activation':myrtle['activation'],'zero_timeline_effect':myrtle['timeline'][0],'no_block_buff':no_block},
        'new_approval_receipt_written':False}


if __name__=='__main__':
    result=audit();out=ROOT/'validation/campaign/c0_first_model_typed_audit.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'implementation':result['implementation_sha256'],'input':result['input_package_sha256'],
        'model_gaps':[g['id'] for g in result['typed_gaps'] if g['type']=='model_gap'],'formal_approval':False,'output':str(out)}))
