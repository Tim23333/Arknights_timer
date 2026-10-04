"""Source INPUT_TARGET2 is hard eligibility of the current blocker."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PINS={'table':'b7eeaa4e415f8fbe613467660af1e899fbd8c57d47a1c090785a6dc00e6d7b31',
      'source_circle':'8a5f768df08686ecffed7036c3e8099e841fc7e4feced0e5db1eebef313b4a77'}
OUT=ROOT/'packages/campaign/chapter04_units/ranged'


def build(policy):
    parent=OUT/(policy+'.reference_model.json');raw=parent.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PINS[policy]:raise ValueError('Frozen ranged source changed')
    p=json.loads(raw);guard='rule/ch4/wizard_combat_guard';bound=[]
    for row in p['manifest']['metadata']['variant_bindings']:
        combat=row['source_combat']
        if combat['native_class']!='RangedAttack' or combat['raw']['_selectTargetSource']!=2:continue
        unit=next(u for u in p['entities'] if u['id']==row['unit_definition'])
        for ident in unit['components']['abilities']:
            ability=next(a for a in p['abilities'] if a['id']==ident);selector=next(s for s in p['selectors'] if s['id']==ability['selector'])
            if selector['eligibility']['rule']!='rule/ch4/ranged_qualification':raise ValueError('Original qualified selector changed')
            selector['eligibility']['rule']=guard;bound.append({'variant_id':row['variant_id'],'ability':ident,'selector':selector['id'],'source_combat':combat})
    if len(bound)!=1:raise ValueError('Expected exactly one Wizard combat INPUT_TARGET2 consumer')
    p['rules'].append({'id':guard,'kind':'rule','contract':'targeting.eligibility',
        'implementation':{'type':'graph','nodes':[{'id':'native_options','rule':'rule/ch4/ranged_qualification',
            'inputs':{name:'inputs.'+name for name in ('source','candidate','selector','selection_states','parameters')}},
            {'id':'result','expression':"{'accepted':nodes.native_options.accepted and ('blocked_by' not in inputs.source.components.runtime or inputs.source.components.runtime.blocked_by == None or inputs.source.components.runtime.blocked_by == inputs.candidate.id),'reason':nodes.native_options.reason if nodes.native_options.accepted == False else 'combat_INPUT_TARGET2'}"}],
            'output':'nodes.result'}})
    for rule in p['rules']:
        if rule['id']=='rule/ch4/ranged_priority':
            rule['implementation']['expression']="0 if 'blocked_by' in inputs.source.components.runtime and inputs.source.components.runtime.blocked_by != None else -100000 * (inputs.candidate.components.attributes.base.taunt_level if 'taunt_level' in inputs.candidate.components.attributes.base else 0) + inputs.distance"
    p['manifest']['id']+='/combat_guard'
    p['manifest']['metadata'].update(parent_module_sha256=PINS[policy],combat_guard_builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        combat_guard_bindings=bound,combat_guard_policy='Hard current-blocker identity AND original eligibility; no geometry/free/type bypass or fallback to others',
        independent_peer_pending=True)
    p['manifest']['metadata']['source_locks'][str(parent.relative_to(ROOT))]=PINS[policy]
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for policy in PINS:
        raw=(json.dumps(build(policy),ensure_ascii=False,indent=2)+'\n').encode('utf8');path=OUT/('combat_guard.'+policy+'.reference_model.json')
        if args.check:
            if path.read_bytes()!=raw:raise ValueError('Corrected module bytes changed')
        else:
            if path.exists():raise FileExistsError('Preserve existing source model')
            path.write_bytes(raw)
        print(json.dumps({'policy':policy,'sha256':hashlib.sha256(raw).hexdigest(),'bound_consumers':1}))
