"""Compose frozen projectiles, declared decisions and sparse source states.

Unknown native getters/statuses remain explicit mathematical policies and
accuracy gaps. No source field or old accepted input is overwritten.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
CORE='7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe'
PLAN=ROOT/'packages/campaign/actor_selection_source/binding.plan.json'
QUAL=ROOT/'packages/campaign/selector_eligibility/m25.source_profiles.json'
M22={'01-11':'ad147b19e709d6dbd0f935c6a4aeb80e5f8dddad744af4ad0829f583cb8dc262','01-12':'a681a1d4fc76e613f658ea3a27fad4cd0ecd0923308f366b2dafe568af9f30ce'}
M24={'01-11':'f641e67cf5cd503948f0d590a04579ba632c06d29ab327140cca551cbc042211','01-12':'4f1d5166ac835cc1996bdc21b25430a92b1d8a233d0d615ca0b98c2f22d5d4b9'}
STATE_MAP={'unit/kalts_mon3tr_model':'token_10002_kalts_mon3tr','unit/support_night_bird':'token_10003_cgbird_bird',
    'unit/campaign_weedy_cannon':'token_10009_weedy_cannon','unit/chapter01_emp':'trap_002_emp','unit/chapter01_w':'enemy_1504_cqbw'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())
def encoded(v):return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')


def npc_source_patch():
    """Actual E0L20 predefined source; never substitute fixed12 data."""
    import UnityPy
    path=ROOT/'packages/campaign/chapter01_sources/native.reference.json';stage=load(path)['stages']['level_main_01-11']
    prefab=stage['predefined_prefab_sources']['char_211_adnach'];asset=ROOT.parent/prefab['source']['path']
    if sha(asset)!=prefab['source']['sha256']:raise ValueError('NPC source CAB drift')
    nodes={o.path_id:o for o in UnityPy.load(str(asset)).objects}
    roots=[(pid,row) for pid,row in prefab['components'].items() if row['native_class']=='Character'
           and row['raw']['m_GameObject']['m_PathID']==prefab['root_gameobject_path_id']]
    if len(roots)!=1:raise ValueError('NPC root Character ambiguous')
    pid,row=roots[0]
    if nodes[int(pid)].read_typetree()!=row['raw'] or row['raw']['_motionMode']!=0:raise ValueError('NPC root motion differs')
    char=stage['predefined_character_sources']['char_211_adnach']
    if char['profession']!='SNIPER':raise ValueError('NPC actual profession differs')
    return {'actor_id':'char_211_adnach','source_literal_selection_state_patch':{'motion':1,'profession':2},
        'source_field_provenance':{'motion':{'native_motion':0,'component':int(pid),'source':deepcopy(prefab['source'])},
            'profession':{'native_profession':'SNIPER','source':str(path.relative_to(ROOT))}},
        'unknown_fields':['side','category','unit_type','target_free','ally_target_free','heal_free','camouflage','can_select_camouflage',
            'abnormal_flags','abnormal_combos','target_free_flags','target_free_combos'],'version_pending':False}


def build(stage):
    parent=ROOT/f'packages/campaign/chapter01_stage_models/m22/level_main_{stage}.partial.json'
    decision=ROOT/f'packages/campaign/chapter01_behavior/m24/level_main_{stage}.decision.partial.json'
    if sha(parent)!=M22[stage] or sha(decision)!=M24[stage]:raise ValueError('Frozen stage parent changed')
    if sha(PLAN)!='3b44789b1a81eb5b52e1f6aac9583bf30efd7cc7a0f3207f1013acc80335042a':raise ValueError('Sparse actor source changed')
    if sha(QUAL)!='8a8cd2a9ee0f17be209b1d97f6619307b010365ca907dcf31e44b5274848a056':raise ValueError('Qualification source changed')
    p=load(parent);d=load(decision);q=load(QUAL);plan=load(PLAN)
    units={e['id']:e for e in p['entities']};dec_units={e['id']:e for e in d['entities']}
    for behavior in d.get('behaviors',[]):
        if behavior['id'].startswith('behavior/m24/'):
            if any(b['id']==behavior['id'] for b in p['behaviors']):raise ValueError('Decision ID collision')
            p['behaviors'].append(deepcopy(behavior))
    for uid,unit in dec_units.items():
        machine=unit['components'].get('behavior',{}).get('machine','')
        if machine.startswith('behavior/m24/'):
            units[uid]['components']['behavior']=deepcopy(unit['components']['behavior'])
    sparse={r['actor_id']:r for r in plan['actors']};sparse['char_211_adnach']=npc_source_patch();state_records=[]
    for uid,unit in units.items():
        # Tags describe this declared content's side, not recovered getters.
        if uid=='unit/chapter01_emp':side=0;unit_type=4
        elif 'enemy' in unit.get('tags',[]):side=1;unit_type=2
        elif 'player' in unit.get('tags',[]):side=0;unit_type=4 if 'token' in unit['tags'] else 1
        else:continue
        actor_id='char_211_adnach' if uid=='unit/ch1_predefined_adnach_e0_l20' else STATE_MAP.get(uid,uid.removeprefix('unit/'));source=sparse.get(actor_id)
        mathematical={'side':side,'motion':2 if 'flying' in unit.get('tags',[]) else 1,'category':1,'profession':0,'unit_type':unit_type,
            'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False,
            'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[]}
        patch=deepcopy(source['source_literal_selection_state_patch']) if source else {}
        state={**mathematical,**patch};unit['components']['selection_state']=state
        record={'unit':uid,'source_actor_id':actor_id,'source_literal_patch':patch,
            'math_policy_fields':{key:value for key,value in mathematical.items() if key not in patch},
            'source_provenance':source['source_field_provenance'] if source else {},
            'unknown_source_fields':source['unknown_fields'] if source else list(mathematical),
            'version_pending':source.get('version_pending',False) if source else True,
            'actual_client_verified':False,'policy':'Explicit side/category/unit-type/status math; no native getter proof'}
        unit.setdefault('metadata',{})['m26_selection_state']=deepcopy(record);state_records.append(record)
    selectors={s['id']:s for s in p['selectors']};bindings=[]
    chains=q['manifest']['metadata']['source_binding_evidence']
    raw_profiles={s['metadata']['actual_component_path_id']:s for s in q['selectors']}
    for chain in chains:
        owner=chain['owner']
        if owner=='enemy_1504_cqbw':
            # Match actual source mode PPtrs against frozen FSM source records.
            source=load(ROOT/'packages/campaign/chapter01_behavior/source.reference.json')['enemies'][owner]
            modes=[r for r in source['mode_links'] if r['mode_path_id']==chain['mode_path_id']]
            if len(modes)!=1:raise ValueError('Exact W mode source missing')
            mode_index=source['mode_links'].index(modes[0]);sid=f'selector/chapter01_w_normal_{mode_index}'
        else:sid=f'selector/{owner}/ch1_model'
        if sid not in selectors:continue
        profile=raw_profiles[chain['unique_same_go_selector_path_id']]
        spec=deepcopy(profile['eligibility']);spec['rule']='rule/m26/source_qualification'
        selectors[sid]['eligibility']=spec
        selectors[sid].setdefault('metadata',{})['m26_source_qualification']={'chain':deepcopy(chain),'source':profile['metadata']['source'],
            'native_actual_correct':False,'scope':'Exact enabled source fields; existing geometry/order and native forwarding remain declared model'}
        bindings.append({'selector':sid,'chain':deepcopy(chain),'source_profile':profile['id']})
    # C4 explicitly names its fifth SecondaryFilterAdvancedSelector; it is
    # not interchangeable with normal mode WALK-only trigger qualification.
    c4_source=raw_profiles[-3353799912320919605]
    native=load(ROOT/'packages/campaign/chapter01_sources/native.reference.json')['enemies']['enemy_1504_cqbw']['prefab']
    attack=native['components']['356424887913093067']['raw']
    if attack['_selector']['m_PathID']!=-3353799912320919605:raise ValueError('C4 explicit selector source changed')
    for mode in (0,1):
        sid=f'selector/chapter01_w_c4_{mode}'
        if sid not in selectors:raise ValueError('C4 active selector absent')
        spec=deepcopy(c4_source['eligibility']);spec['rule']='rule/m26/source_qualification';selectors[sid]['eligibility']=spec
        evidence={'ranged_attack_path_id':356424887913093067,'explicit_selector_path_id':-3353799912320919605,
                  'actual_source_configuration':deepcopy(c4_source['eligibility']['parameters']['source_configuration'])}
        selectors[sid].setdefault('metadata',{})['m26_source_qualification']={'chain':evidence,'source':c4_source['metadata']['source'],
            'native_actual_correct':False,'scope':'Exact C4 explicit selector; SecondaryFilter comparator native body pending'}
        bindings.append({'selector':sid,'chain':evidence,'source_profile':c4_source['id']})
    rule=deepcopy(q['rules'][0]);rule['id']='rule/m26/source_qualification';p.setdefault('rules',[]).append(rule)
    meta=p['manifest']['metadata'];meta['m26_content']={'builder_sha256':sha(__file__),'parent_m22':sha(parent),'decision_m24':sha(decision),
        'actor_plan':sha(PLAN),'qualification_source':sha(QUAL),'required_core':CORE,'actor_states':state_records,'selector_bindings':bindings,
        'declared_math_policy':True,'native_actual_correct':False,'client_pending':['Unknown actor side/category/unit-type/status getters and selected live writers',
            'Source-relative side interpretation and target forwarding method body','Source version correspondence and native geometry/order']}
    meta['required_runtime']=CORE;meta['source_locks'].update({str(PLAN.relative_to(ROOT)).replace('\\','/'):sha(PLAN),str(QUAL.relative_to(ROOT)).replace('\\','/'):sha(QUAL)})
    meta['pending_model_gaps']=list(dict.fromkeys(meta['pending_model_gaps']+['m26_actor_unknown_getters_and_status_math_policy_client_pending']))
    p['manifest']['id']+='/m26_source_qualification';p['scenarioDraft']['id']+='/m26_source_qualification'
    if stage=='01-11':
        from tools.build_chapter01_roster_policy import apply_fixed12_overlay
        # Preserve explicit native teaching-card versus selected12 distinction.
        p=apply_fixed12_overlay(p);p['manifest']['metadata']['required_runtime']=CORE
        p['manifest']['metadata']['m26_content']['training_overlay']='Explicit fixed12 test override; native cards retained in source metadata'
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    sys.path.insert(0,str(RUNTIME));from ark_sim import Compiler;from ark_sim.adapters.api import implementation_digest
    if implementation_digest()!=CORE:raise ValueError('Frozen M26 changed')
    rows=[]
    for stage in M22:
        p=build(stage);program=Compiler().compile(p);out=ROOT/f'packages/campaign/chapter01_stage_models/m26/level_main_{stage}.partial.json'
        if args.check:
            if out.read_bytes()!=encoded(p):raise ValueError('M26 content drift')
        else:out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(encoded(p))
        rows.append({'stage':stage,'sha256':sha(out),'definitions':len(program.definitions),'native_actual_correct':False})
    print(json.dumps(rows))
