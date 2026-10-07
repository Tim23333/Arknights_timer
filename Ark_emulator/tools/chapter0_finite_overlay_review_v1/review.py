"""Independent of Root's finite overlay writer; static metadata/command audit."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter0_finite_overlay_review_v1/review.v1.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def exact(a,b,path='root'):
    if type(a)is not type(b):raise ValueError('Type mismatch '+path)
    if isinstance(a,dict):
        if set(a)!=set(b):raise ValueError('Keyset mismatch '+path)
        for k in a:exact(a[k],b[k],path+'.'+k)
    elif isinstance(a,list):
        if len(a)!=len(b):raise ValueError('Length mismatch '+path)
        for i,(x,y) in enumerate(zip(a,b)):exact(x,y,path+'['+str(i)+']')
    elif a!=b:raise ValueError('Value mismatch '+path)
def main():
    folder=ROOT/'validation/campaign/chapter0_stage_assembly_v1';overlay_path=folder/'runthrough.overlay.v1.json';queue_path=folder/'queue.admission.v2.json';o=json.loads(overlay_path.read_bytes());q=json.loads(queue_path.read_bytes());pins={str(overlay_path):sha(overlay_path),str(queue_path):sha(queue_path)}
    assert o['queue_sha256']==sha(queue_path)
    assert q['whole_stages_passed'] is False and q['client_verified'] is False and o['whole_stage_passed'] is False and o['no_new_simulation'] is True
    receipts={}
    for name,ref in q['consumed_receipts'].items():
        assert sha(ref['path'])==ref['sha256'];pins[ref['path']]=ref['sha256'];receipts[name]=json.loads(Path(ref['path']).read_bytes())
    assert receipts['source_peer']['source_input_approved'] is True and receipts['plan_peer']['static_plan_intent_approved'] is True
    for path,h in receipts['source_peer']['current_source_guards'].items():assert sha(path)==h;pins[path]=h
    for path,h in receipts['prefix']['source_guards'].items():assert sha(path)==h;pins[path]=h
    assert receipts['plan_peer']['actual_command_acceptance_approved'] is False and receipts['prefix']['passed'] is True
    assert all(q['explicit_approvals_and_current_guard_checks'].values());rows=[]
    for entry in o['records']:
        stage=entry['stage'];base=next(c for c in q['cases'] if c['stage']==stage)
        for path,h in [(entry['package'],entry['package_sha256']),(entry['commands'],entry['commands_sha256']),(base['package'],base['package_sha256']),(base['public_plan'],base['public_plan_sha256'])]:assert sha(path)==h;pins[path]=h
        assert entry['parent_sha256']==base['package_sha256'] and entry['source_plan_sha256']==base['public_plan_sha256']
        original=json.loads(Path(base['package']).read_bytes());wrapped=json.loads(Path(entry['package']).read_bytes());flat=json.loads(Path(entry['commands']).read_bytes());plan=json.loads(Path(base['public_plan']).read_bytes());profile=wrapped['scenarioDraft']['metadata'].pop('runthrough_profile');exact(original,wrapped);exact(flat,plan['commands']);assert len(flat)==70
        assert profile['base_life_resource']=='life' and type(profile['base_life'])is int and profile['base_life']==99999 and type(profile['source_births'])is int and profile['source_births']==base['source_births']==(35 if stage.endswith('10') else 37)
        exact(profile['fixed12'],original['scenarioDraft']['roster']);assert profile['deploy_capacity']==original['scenarioDraft']['parameters']['deploy_capacity']==8
        assert profile['training_deployment_exception'] is False and profile['client_verified'] is False and profile['public_dialogue_driver_required'] is True and profile['public_commands_sha256']==entry['commands_sha256']
        assert original['scenarioDraft']['resources']['dp']['initial']==10 and len(profile['fixed12'])==12 and base['whole_started'] is entry['whole_started'] is False
        counts={k:sum(c['action']==k for c in flat) for k in ('deploy','withdraw','skill')};assert counts=={'deploy':12,'withdraw':5,'skill':53}
        rows.append({'stage':stage,'only_scene_runthrough_profile_added':True,'original_source_typed_restored_equal':True,'all_70_commands_typed_equal_V5':True,'counts':counts,'births':base['source_births'],'DP':10,'capacity':8,'fixed_roster':12,'controls_actor_values_routes_RNG_preserved':True,'source_bytes_modified':False,'whole_started':False})
    assert len(rows)==2 and all(sha(p)==h for p,h in pins.items());result={'schema':'ark-sim/chapter0-finite-overlay-independent-static/v1','overlay_static_approved':True,'rows':rows,'source_guards':pins,'source_guards_current':True,'queue_receipt_consumed':str(queue_path),'reviewer_sha256':sha(Path(__file__)),
      'scope':'Independent audit of Root metadata-only overlays and flattening only. Reviewer authored original source stages; existing separate source/plan peers supply original input review, never replaced by this check. No runtime started or whole-stage/native/client acceptance.','original_source_third_party_claim':False,'simulation_started':False,'whole_stage_passed':False,'client_verified':False}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'approved':True,'sha256':sha(OUT),'counts':rows[0]['counts']}))
if __name__=='__main__':main()
