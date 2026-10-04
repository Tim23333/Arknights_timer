"""Normal caster INPUT_TARGET2 qualifies actual blocker; lasso stays distinct."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'packages/campaign/chapter04_dmage/module.reference.json'
PIN='90e091ba8677527c4f7bb68fc5cbbbc47fd29d32c1837bed7d02fb0493aa1c6e'
SOURCE=ROOT/'packages/campaign/chapter04_dmage/source.reference.json'
SOURCE_PIN='bac0af413f5a2380e623c180e3c8b8c1852e2a425e4058e8c0f0ec217eb34681'
OUT=ROOT/'packages/campaign/chapter04_dmage/module.combat_guard.reference.json'


def build():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PIN or hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SOURCE_PIN:
        raise ValueError('Frozen lasso source/module changed')
    p=json.loads(PARENT.read_bytes());guard='rule/ch4/dmage_combat_guard'
    normal=[a for a in p['abilities'] if a['id'].endswith('/normal')]
    if len(normal)!=1:raise ValueError('Exact ordinary ability binding required')
    selected=next(s for s in p['selectors'] if s['id']==normal[0]['selector'])
    if selected['eligibility']['rule']!='rule/ch4/dmage_eligibility':raise ValueError('Original qualification changed')
    selected['eligibility']['rule']=guard
    p['rules'].append({'id':guard,'kind':'rule','contract':'targeting.eligibility','implementation':{'type':'graph',
        'nodes':[{'id':'native_options','rule':'rule/ch4/dmage_eligibility','inputs':{k:'inputs.'+k for k in ('source','candidate','selector','selection_states','parameters')}},
            {'id':'result','expression':"{'accepted':nodes.native_options.accepted and ('blocked_by' not in inputs.source.components.runtime or inputs.source.components.runtime.blocked_by == None or inputs.source.components.runtime.blocked_by == inputs.candidate.id),'reason':nodes.native_options.reason if nodes.native_options.accepted == False else 'combat_INPUT_TARGET2'}"}],
        'output':'nodes.result'}})
    p['manifest']['id']+='/combat_guard'
    p['manifest']['metadata'].update(parent_module_sha256=PIN,combat_guard_builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        combat_guard_binding={'ability':normal[0]['id'],'selector':selected['id'],'source_variant':'enemy_1022_dmage@0/ed10af8ce8e1725f'},
        combat_guard_policy='Only ordinary RangedCombat INPUT_TARGET2; current blocker hard eligibility, source options/range retained; lasso selection unchanged',independent_peer_pending=True)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Combat source output changed')
    else:
        if OUT.exists():raise FileExistsError('Preserve content identity')
        OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'ordinary_guard':True,'lasso_changed':False}))
