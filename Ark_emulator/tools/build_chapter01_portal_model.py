"""New 1-12 portal/terrain wrapper, preserving the frozen partial parent."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT.parent/'unpack_work/campaign_m18_portal_candidate'
BASE=ROOT/'packages/campaign/chapter01_stage_models/level_main_01-12.partial.json'
EMP=ROOT/'packages/campaign/chapter01_devices/emp.terrain.json'
AUDIT=ROOT/'validation/campaign/chapter01_portal_source_audit.json'
OUTPUT=ROOT/'packages/campaign/chapter01_stage_models/m18/level_main_01-12.portal.partial.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core_digest():
    files={str(p.relative_to(CANDIDATE/'ark_sim')):sha(p) for p in sorted((CANDIDATE/'ark_sim').rglob('*.py'))}
    return hashlib.sha256(json.dumps(files,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def build():
    assert sha(BASE)=='ffc71f7aeb3644a9ad4c868b41a7b510435e369f20cc2a938ff8d1f7681705fd'
    assert sha(EMP)=='362c2fb4a102197ff23b6ff48379c8940a98127bbfb6848b6ab4e837f673edb2'
    assert sha(AUDIT)=='65180c96d812a6155144026c42ca54350eb9e03b358c0f3562d9bf348562a339'
    p=json.loads(BASE.read_bytes());e=json.loads(EMP.read_bytes());a=json.loads(AUDIT.read_bytes())
    m=p['manifest']['metadata'];m['required_runtime']=core_digest()
    m['m18_portal_wrapper']={'builder_sha256':sha(Path(__file__)),'parent_stage_sha256':sha(BASE),
        'EMP_terrain_sha256':sha(EMP),'portal_source_audit_sha256':sha(AUDIT),'formal_approval':False,
        'model_profile':'Only authored route checkpoint transitions; no automatic entry or inferred exit',
        'client_pending':['Generic Tile/Enemy native method body and key dispatch','native height/cost/visual callback/version correspondence']}
    profiles={}
    for association in a['route_associations']:
        for key,role in ((association['entry_tile'],'entry'),(association['exit_tile'],'exit')):
            expected={'type':'route_checkpoint_portal','role':role}
            if key in profiles:assert profiles[key]==expected
            profiles[key]=expected
    p['scenarioDraft']['map']['tile_mechanics']=profiles
    for t in p['scenarioDraft']['map']['tiles']:
        if t['tileKey'] in profiles:assert not t.get('blackboard') and not t.get('effects')
    replacements={x['id']:x for x in e['entities']}
    p['entities']=[deepcopy(replacements.get(x['id'],x)) for x in p['entities']]
    # Remove precisely these two consumed execution gaps, retaining all unrelated
    # projectile/FSM/whole-stage gates and adding the explicit 2D source boundary.
    consumed={'EMP_owned_terrain_layers_not_in_this_runtime','native_tile_telin_telout_requires_explicit_mechanics_profile'}
    m['consumed_m18_gap_ids']=sorted(consumed)
    m['pending_model_gaps']=[x for x in m['pending_model_gaps'] if x not in consumed]+['3D_physical_height_outside_2D_model']
    m['model_profiles']['EMP']='category_filtered_skill_retire_owned_terrain_partial'
    p['manifest']['id']+='/m18_portal';p['status']='partial_stage_portal_route_and_terrain_model'
    return p
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();j=build();raw=(json.dumps(j,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if a.check:assert OUTPUT.read_bytes()==raw,'M18 portal wrapper changed'
    else:OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_bytes(raw)
    print(json.dumps({'path':str(OUTPUT),'sha256':sha(OUTPUT),'core':j['manifest']['metadata']['required_runtime'],'profiles':j['scenarioDraft']['map']['tile_mechanics']}))
