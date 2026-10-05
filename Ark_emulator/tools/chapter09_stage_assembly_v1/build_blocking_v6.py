"""Bind the native obstacle radius at the contract's actual scenario owner."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    parent=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v5.life99999.json'
    p=json.loads(parent.read_bytes());scene=p['scenarioDraft'];base=scene.get('rules',{}).get('blocking.eligibility','rule/ark_block_eligibility')
    body=next(d for d in p['definitions'] if d['id']=='unit/ch9/pillar/ruin')
    unused=body['rules'].pop('blocking.eligibility');assert unused=='rule/ch9/ruin/blocking'
    if not body['rules']:body.pop('rules')
    rule={'id':'rule/ch9/scenario_blocking','kind':'rule','contract':'blocking.eligibility',
        'parameters':{'base_rule':base,'ruin':{'definition':body['id'],'radius_squared':body['metadata']['source_block_radius_squared']}},
        'implementation':{'type':'provider','provider':'reference.ch9.scenario_blocking'},'dependencies':[base]}
    scene.setdefault('rules',{})['blocking.eligibility']=rule['id'];p['definitions'].append(rule)
    p['manifest']['metadata']['scenario_owned_blocking']={'parent_sha':hashlib.sha256(parent.read_bytes()).hexdigest(),'contract_owner':'scenario','ignored_old_entity_binding':unused,'base_rule_preserved':base,'actual_radius_rule_proof_required':True,'whole_stage':False}
    out=parent.with_name('level_main_09-16.native_draft.v6.life99999.json');assert not out.exists();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
