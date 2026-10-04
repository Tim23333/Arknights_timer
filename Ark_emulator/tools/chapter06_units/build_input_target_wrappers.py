"""New content-only INPUT_TARGET2 gates actual blocker without finite score hacks."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(source,pin,version):
    if sha(source)!=pin:raise ValueError('Frozen original content identity differs')
    p=json.loads(source.read_bytes());p['manifest']['id']+='/input_target_'+version;m=p['manifest']['metadata']
    m['source_locks'][str(source.relative_to(ROOT))]=pin
    m['input_target_wrapper_builder_sha256']=sha(Path(__file__))
    m['input_target2_policy']={'source':'Native _selectTargetSource2 INPUT_TARGET; original native eligibility must remain true','blocked':'Current runtime.blocked_by!=None gates exact candidate.id equality, nopriorityconstant','invalid':'If an existing blocker fails original eligibility, noothercandidate is admitted; genuine released relation(None) restores ordinaryunblocked range','first_cast':'Each real attack activation.settle_blocking=True settles current relation before spatialselect','unblocked':'Original region/side/motion/category/targetfree/camouflage/hate rules retained','native_body_verified':False,'source_hardgate_consumed':True}
    wrappers=[]
    for selector in p['selectors']:
        if not selector.get('eligibility'):continue
        native=selector['eligibility']['rule'];ident=native+'/input_target2'
        if ident not in wrappers:
            p['rules'].append({'id':ident,'kind':'calculation_rule','contract':'targeting.eligibility','dependencies':[native],'implementation':{'type':'graph','nodes':[{'id':'base','rule':native,'inputs':{k:'inputs.'+k for k in ('source','candidate','selector','selection_states','parameters')}},{'id':'gate','expression':"nodes.base.accepted and ('blocked_by' not in inputs.source.components.runtime or inputs.source.components.runtime.blocked_by == None or inputs.candidate.id == inputs.source.components.runtime.blocked_by)"},{'id':'result','expression':"{'accepted':nodes.gate,'reason':nodes.base.reason if nodes.gate else 'native_eligibility_or_input_target_blocker'}"}],'output':'nodes.result'}})
            wrappers.append(ident)
        selector['eligibility']['rule']=ident
    for ability in p['abilities']:
        ability['activation']['settle_blocking']=True
    m['input_target2_wrapper_rules']=wrappers
    return p
if __name__=='__main__':
    for file,pin,out,version in [('snmage_v2/model.json','6ec20811b5a6728078979b8c61fc8976833cc944a5232c086c2044bae5926f56','snmage_v3/model.json','v3'),('snbow/model.json','f8ebd5faf1d7bf68b96c809de7aaf6b291a76bc202adc15f6ca34d17eaddd555','snbow_v2/model.json','v2')]:
        source=ROOT/'packages/campaign/chapter06_units'/file;dest=ROOT/'packages/campaign/chapter06_units'/out;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((json.dumps(build(source,pin,version),ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps({'path':str(dest),'sha256':sha(dest)}))
