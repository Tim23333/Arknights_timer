import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
paths=['validation/campaign/m94_complete_c4/full_v2_verification.json',
       'validation/campaign/m94_complete_c4/full49_v3.json',
       'validation/campaign/tile_targets_v1/author_tests_v7.json',
       'validation/campaign/tile_targets_v1/compat_v7.json',
       'validation/campaign/tile_targets_v1/freeze_v7.json',
       'packages/campaign/chapter04_boss/ice_shield_v3/module.reference.json']
def main():
    receipts={p:{'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in paths}
    suite=json.loads((ROOT/paths[0]).read_bytes());full=json.loads((ROOT/paths[1]).read_bytes())
    assert suite['exitcode']==0 and all(c['outcome']=='passed' for c in suite['cases'])
    assert full['passed'] and full['process_complete'] and full['checkpoint_equal'] and full['durable_checkpoint_equal'] and full['replay_equal'] and full['identity_stable']
    data={'goal_status':'active','reference_first_user_instruction':True,'client_verified':False,
        'base_life':99999,'unit_hp_unchanged':True,'formal_accepted':1,'target_count':36,
        'receipts':receipts,'m94_fullsuite_passed_cases':len(suite['cases']),
        'old_v3_4_9_complete_with_known_source_gap':True,
        'pending':{'4_9_m96_v6':{'session_id':23154,'locator_only':True},
                   '1_11_m48_v17':{'session_id':38724,'locator_only':True},
                   '3_7_m82_v16':{'session_id':47821,'locator_only':True},
                   'tile_v7':'Independent peer then Frost candidate composition',
                   '4_10':'43 births/source module compilation and full process pending'},
        'registry_policy':'Official registry unchanged during V17 guards; no migration of old proofs'}
    target=ROOT/'validation/campaign/reference_first_tile_increment_20261003.json'
    with target.open('x',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    print(json.dumps({'receipt':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
if __name__=='__main__':main()
