"""Read-only actor body/source binding; independent of runtime calculators."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.compare_campaign_trace import exact,integer


def audit(journal,package):
    definitions={d['id']:d for d in package.get('definitions',[])}
    for key in ['entities','buffs','abilities','selectors','rules']:
        definitions.update({d['id']:d for d in package.get(key,[])})
    actors={};pending=Counter();counts=Counter();failures=[]
    def fail(e,field,want,actual):
        counts['failed']+=1
        if len(failures)<50:failures.append({'event':e['id'],'time':e['time'],'field':field,'expected':want,'actual':actual})
    def body(e,value,role,expected):
        if expected is None:
            if value not in ({},None):fail(e,role+'.body',{},value)
            return
        try:
            integer(expected,role+' actor')
            if expected<1:raise ValueError('positive actor required')
        except ValueError:fail(e,role+'.actor','strict positive actor ID',expected);return
        if not isinstance(value,dict) or not exact(value.get('id'),expected):
            fail(e,role+'.body.id',expected,value.get('id') if isinstance(value,dict) else value);return
        ident=value.get('definition_id')
        if expected in actors and actors[expected]!=ident:fail(e,role+'.body.definition',actors[expected],ident)
        elif expected not in actors:pending['actor.body.before_birth_announcement']+=1
        definition=definitions.get(ident)
        if definition is None:pending['actor.definition.absent_from_input']+=1;return
        counts['actor_body_identity_checked']+=1
        sourcebase=definition.get('components',{}).get('attributes',{}).get('base',{})
        actualbase=value.get('components',{}).get('attributes',{}).get('base',{})
        if not exact(sourcebase,actualbase):fail(e,role+'.attributes.base',sourcebase,actualbase)
        else:counts['source_attribute_base_checked']+=1
    with Path(journal).open(encoding='utf8') as f:
        for line in f:
            e=json.loads(line);counts['events']+=1;v=e.get('payload',{})
            if e['type'] in ('entity.created','entity.registered'):
                ref=v.get('target');integer(ref,'birth target');ident=v['definition']
                if ref<1:raise ValueError('positive birth target required')
                if ident not in definitions:fail(e,'birth.definition','declared input definition',ident)
                if ref in actors and actors[ref]!=ident:fail(e,'birth.actor.definition',actors[ref],ident)
                actors[ref]=ident;counts['birth_identity_checked']+=1
            if e['type']!='calculation':continue
            trace=v.get('trace',{});inputs=trace.get('inputs',{});ctx=trace.get('context',{})
            for role in ('source','target','owner'):
                if role in inputs:body(e,inputs[role],role,ctx.get(role+'_id'))
    return {'passed':not failures,'counts':dict(counts),'pending_fields':dict(pending),'failures':failures,
            'scope':'Captured entity IDs/definitions/base fields vs actual source input. Runtime modifiers, effective attributes, dynamic base edits, birth HP/resource initialization still require separate contracts.',
            'all_fields_independently_verified':False,'client_verified':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--journal',type=Path,required=True);p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists();r=audit(a.journal,json.loads(a.package.read_bytes()))
    r['package_sha']=hashlib.sha256(a.package.read_bytes()).hexdigest();r['helper_sha']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'passed':r['passed'],'counts':r['counts'],'pending':r['pending_fields'],'failures':r['failures'][:2]}));raise SystemExit(0 if r['passed'] else 1)


if __name__=='__main__':main()
