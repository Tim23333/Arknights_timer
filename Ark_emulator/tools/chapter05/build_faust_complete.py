"""Faust three-ability consumer requires an actual source branch program."""
import argparse,hashlib,json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
COMBAT=ROOT/'packages/campaign/chapter05_boss/faust/combat.v4.reference.json'
AUDIT=ROOT/'packages/campaign/chapter05_boss/faust/source.audit.json'
BRANCH=ROOT/'packages/campaign/chapter05_boss/faust/branch.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert sha(COMBAT)=='357abc09e1aa12410d36353769cf8f0c7416fcd12c1556098d01e6c0c7855ee4'
    assert sha(AUDIT)=='70171c9be4ce650b9968b173c84ca05d5b5d227dedae29745d5d8fe29e6a666d'
    assert sha(BRANCH)=='2447fa97a705ab7fa168fbef6dfa39ed5c2d2c9c1d6f2fb1864d56804bb55c66'
    p=deepcopy(json.loads(COMBAT.read_bytes()));audit=json.loads(AUDIT.read_bytes());db=audit['variant']['native_enemy']['resolved']
    skill=next(s for s in db['skills'] if s['prefabKey']=='SummonBallis');anim=audit['animation_events']['animations']['Skill_2']
    assert (skill['priority'],skill['cooldown'],skill['initCooldown'],anim['events'][0]['frame'],anim['duration']['frame'])==(1,30,15,27,50)
    ident='ability/ch5/faust/summon_ballis';branch='faust_ballis'
    p['abilities'].append({'id':ident,'kind':'ability','initial_cooldown_seconds':15,'cooldown_seconds':30,
        'duration_seconds':50/30,'activation':{'mode':'manual','condition':"inputs.branches['faust_ballis'].available",
            'parameters':{'auto_only':True,'requires_targets':False}},'timeline':[{'at':27,
            'effect':{'op':'advance_branch','parameters':{'branch':branch}}}],
        'metadata':{'source_skill':skill,'source_animation':anim,'source_nodes':audit['decoded_actions']}})
    unit=p['entities'][0];unit['components']['abilities'].append(ident)
    unit['components']['ability_arbitration']['entries'].insert(0,{'ability':ident,'priority':1,'attack_clock':True,
        'require_attack_control':True,'condition':"inputs.branches['faust_ballis'].available",'parameters':{}})
    group=p['behaviors'][0]['decision']['profiles'][0]['cast_groups'][0];group['abilities'].append(ident)
    meta=p['manifest']['metadata'];meta.update(status='three_ability_consumer_pending_peer_ballista_and_fullstage',
        source_locks={str(x.relative_to(ROOT)):sha(x) for x in (COMBAT,AUDIT,BRANCH)},builder_sha=sha(Path(__file__)),
        branch_program=json.loads(BRANCH.read_bytes()),
        policies={**meta['policies'],'summon_clock':'15s initial/30s after Skill_2 finishes, higherpriority1/shared5s attack clock; explicit reference pending loader calibration',
            'branch_scope':'Battle-owned accepted phase requests; no request once7phase exhausted; actual source branch programs required'},
        pending=['Actual ballista attacks/movement/collision','Independent fullconsumer and5-10stage'])
    p['manifest']['id']='package/ch5/faust/complete_reference_v1'
    return p
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    out=ROOT/'packages/campaign/chapter05_boss/faust/complete.v2.reference.json'
    if args.check:assert out.read_bytes()==raw
    else:
        with out.open('xb') as f:f.write(raw)
    print(json.dumps({'sha':hashlib.sha256(raw).hexdigest(),'full_stage_executed':False}))
if __name__=='__main__':main()
