"""Qualify both native STUN0 control contributions by effective status."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'packages/campaign/chapter04_dmage/module.combat_guard.reference.json'
PIN='0833e8e9601fc390486b72a0878c6e94229d28bfef084b741127764c32b64465'
OUT=ROOT/'packages/campaign/chapter04_dmage/module.immunity_guard.reference.json'


def build():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PIN:raise ValueError('Frozen source2 wrapper changed')
    p=json.loads(PARENT.read_bytes());rule='rule/ch4/dmage_stun_control';rows=[]
    for buff in p['buffs']:
        if buff.get('selection_flags',{}).get('abnormal_flags')!=[0]:continue
        if 'control_rule' in buff:raise ValueError('Unexpected existing native control consumer')
        buff['control_rule']=rule;rows.append(buff['id'])
    if len(rows)!=2:raise ValueError('Exact caster hold and target STUN0 contributions required')
    p['rules'].append({'id':rule,'kind':'rule','contract':'buff.applicability',
        'implementation':{'type':'expression','expression':'0 in inputs.status.abnormal_flags'}})
    p['manifest']['id']+='/immunity_control'
    p['manifest']['metadata'].update(parent_immunity_module_sha256=PIN,immunity_guard_builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        qualified_control_buffs=rows,required_contracts=['buff.applicability'],immunity_control_policy='Only STUN0 control gated by effective abnormal flag; Buff lease, BUFF damage and non-STUN end recovery retained',
        independent_immunity_peer_pending=True)
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Immunity source model changed')
    else:
        if OUT.exists():raise FileExistsError('Preserve content identity')
        OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'STUN0_control_contributions':2,'damage_unchanged':True}))
