"""Receiver rule output, denial, current applicability and holder-only writes."""
import argparse
from pathlib import Path
import sys,json,traceback,hashlib,copy,os

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--core',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    from ark_sim.tools.replay import replay
    assert implementation_digest()==args.core
    seen=[]
    def request(inputs,params,context):
        assert context['owner']['id']==context['target']['id']==inputs['target']['id']
        assert context['source']['id']==inputs['source']['id']
        if params.get('reject'):return {'accepted':False,'effect':dict(inputs['effect']),'effects':[]}
        effects=[{'op':'emit','event':'receiver.pre','payload':{'source_id':inputs['source']['id'],'holder_id':inputs['target']['id']}}]
        if params.get('illegal'):effects=[{'op':'damage','damage_type':'true','scale':100}]
        if params.get('wrongtarget'):effects[0]['target']=999
        seen.append(context['time'])
        return {'accepted':True,'effect':dict(inputs['effect']),'effects':effects}
    reg={**BUILTIN_PROVIDERS,'peer.receiver/request':{'callable':request,'version':'independent-source-scope-1'}}
    def data(**options):
        d={'schemaVersion':2,'entities':[],'buffs':[{'id':'buff/receiver/protocol','kind':'buff','damage_hooks':[{'phase':'receiver_request','rule':'rule/receiver/request','after_effects':[{'op':'emit','event':'receiver.post'}]}]}],
            'rules':[{'id':'rule/receiver/request','kind':'rule','contract':'damage.request','parameters':options,'implementation':{'type':'provider','provider':'peer.receiver/request'}}],
            'abilities':[{'id':'ability/receiver/protocol/hit','kind':'ability','activation':{'mode':'manual'},'selector':'selector/receiver/protocol','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}],
            'selectors':[{'id':'selector/receiver/protocol','kind':'selector','region':{'type':'all'},'filters':[{'tag':'receiver'}]}],
            'scenarioDraft':{'id':'scene/receiver/protocol','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},'initialEntities':[
                {'definition':'unit/receiver/source','instanceAlias':'source','position':{'row':0,'col':0}},
                {'definition':'unit/receiver/target','instanceAlias':'target','position':{'row':0,'col':1}}],
                'commands':[{'at':11,'action':'skill','source':'source','ability':'ability/receiver/protocol/hit'}]}}
        for name,hp,atk in [('source',319,73),('target',977,0)]:
            d['entities'].append({'id':'unit/receiver/'+name,'kind':'entity','tags':['receiver'] if name=='target' else [],'components':{
                'attributes':{'base':{'max_hp':hp,'atk':atk,'def':0,'mres':0}},'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'spatial':{},
                **({'abilities':['ability/receiver/protocol/hit']} if name=='source' else {'buffs':{'initial':['buff/receiver/protocol']}})}})
        return d
    def create(d):return Engine.create(Compiler(providers=reg).compile(d),providers=reg,seed=12)
    results=[];before_core=implementation_digest();artifacts=[]
    def normal():
        s=create(data());s.advance(12);events=[e for e in s.session.events if e['type'] in ('receiver.pre','resource.changed','damage.accepted','receiver.post') and e['time']==11]
        pre=next(e for e in events if e['type']=='receiver.pre');post=next(e for e in events if e['type']=='receiver.post');change=next(e for e in events if e['type']=='resource.changed' and e['payload']['resource']=='hp');assert pre['id']<change['id']<post['id'];assert s.ctx.resources.current('target','hp')==904
        q=Path(os.environ['ARKSIM_RUN_DIR'])/'protocol.checkpoint.json';q.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(s.program,json.loads(q.read_bytes()),providers=reg);s.advance(20);r.advance(20);h=replay(s.program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==h.checkpoint();artifacts.append({'path':str(q),'sha':hashlib.sha256(q.read_bytes()).hexdigest(),'CPP_head':True})
    def denied():
        s=create(data(reject=True));s.advance(12);assert s.ctx.resources.current('target','hp')==977;assert not any(e['type'] in ('receiver.pre','receiver.post','damage.accepted') for e in s.session.events)
    def illegal():
        for options in ({'illegal':True},{'wrongtarget':True}):
            s=create(data(**options));before=s.checkpoint()
            try:s.ctx.effects.execute('source',['target'],{'op':'damage','damage_type':'true','scale':1})
            except ValueError:pass
            else:raise AssertionError('Foreign receiver hook write accepted')
            assert s.checkpoint()==before
    def inactive():
        d=data();d['buffs'][0]['active_rule']='rule/receiver/inactive';d['rules'].append({'id':'rule/receiver/inactive','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'False'}});s=create(d);s.advance(12);assert s.ctx.resources.current('target','hp')==904;assert not any(e['type'] in ('receiver.pre','receiver.post') for e in s.session.events)
    for name,fn in [('pureholder_scope_and_actual_pre_post_CPPhead',normal),('denied_request_no_writes_damage_or_cleanup',denied),('foreign_effect_operation_or_target_atomicreject',illegal),('inactive_receiver_flags_do_not_run_hook',inactive)]:
        try:fn();results.append({'case':name,'passed':True})
        except Exception as error:results.append({'case':name,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    report={'core':args.core,'actual_exit':0 if all(x['passed'] for x in results) else 1,'results':results,'core_before':before_core,'core_after':implementation_digest(),'artifacts':artifacts,'comparison_exclusions':[]};args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');return report['actual_exit']


if __name__=='__main__':raise SystemExit(main())
