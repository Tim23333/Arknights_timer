"""Fresh context-sensitive plan/clock and legacy-path checks on final V2."""
import copy,json,traceback
import test_depletion_v2 as base
from test_depletion_v2 import Compiler,Engine,implementation_digest,BUILTIN_PROVIDERS,OUT,cp
from ark_sim.tools.replay import replay

OBS=[]
def contextual(inputs,params,context):
    assert context['owner']['id']==inputs['target']['id']
    assert context['target']['id']==inputs['target']['id']
    assert context['source']['id']==inputs['source']['id']
    assert context['time']==inputs['clock']['time']
    assert context['rule_scope']['owner']=={} and context['rule_scope']['source']=={}
    ticks=context.calculate('time.quantize',{'seconds':2,'quantum':inputs['clock']['quantum'],'rounding':{'mode':'ceil'}}).value
    assert ticks==120
    OBS.append({'time':context['time'],'owner':context['owner']['id'],'source':context['source']['id'],'ticks':ticks})
    return base.policy(inputs,params,context)

def custom_context_clock_cpp_head():
    d=base.data();d['rules'][0]['implementation']={'type':'provider','provider':'reference/contextual'}
    # The provider sits under a graph node; both traces must be reproducible.
    d['rules'][0]['id']='rule/depletion/provider'
    d['rules'].append({'id':'rule/depletion/plan','kind':'rule','contract':'resource.depletion','implementation':{'type':'graph','nodes':[{'id':'p','rule':'rule/depletion/provider','inputs':{k:'inputs.'+k for k in ['source','target','request','state','clock','parameters']}}],'output':'nodes.p'}})
    d['rules'].append({'id':'rule/depletion/slowclock','kind':'rule','contract':'time.quantize','implementation':{'type':'expression','expression':'ceil(inputs.seconds / inputs.quantum) * 2'}})
    d['scenarioDraft']['rules']={'time.quantize':'rule/depletion/slowclock'}
    d['scenarioDraft']['commands']=[{'at':3,'action':'skill','source':'source','ability':'ability/depletion/hit'}]
    providers={**base.registry(),'reference/contextual':{'callable':contextual,'version':'1'}}
    program=Compiler(providers=providers).compile(d);s=Engine.create(program,providers=providers,seed=901)
    s.session.advance(4);state=s.ctx.depletion.state('target');assert state['stage']=='damaged' and state['lease']['started']==3
    assert state['lease']['actions']['1']['due']==123
    checkpoint=cp(s);r=Engine.restore(program,checkpoint,providers=providers)
    s.session.advance(119);r.session.advance(119);assert s.ctx.depletion.state('target')['stage']=='damaged'
    s.session.advance(1);r.session.advance(1);assert s.ctx.depletion.state('target')['stage']=='ready' and cp(s)==cp(r)
    h=replay(program,s.export_replay(),providers=providers);assert cp(h)==cp(s)
    assert len(OBS)==3 and all(x['time']==3 for x in OBS)

def legacy_no_optin():
    d=base.data();d['entities'][1]['components'].pop('depletion');d['rules']=[{'id':'rule/legacy/no_source','kind':'rule','contract':'damage.pipeline','implementation':{'type':'expression','expression':"{'accepted': True, 'amount': inputs.effect.fixed_amount, 'allocations': [], 'events': []}"}}]
    s=base.sim(d);assert s.ctx.depletion is None
    s.ctx.effects.execute(None,['target'],{'op':'no_source_damage','damage_type':'true','fixed_amount':60,'attack_type':'NONE','damage_without_modify':True,'origin':{'kind':'reference'},'rules':{'damage.pipeline':'rule/legacy/no_source'},'ignore_for_sp':False,'node_is_env_damage':False,'env_blackboard_injected':False,'environmental':False})
    assert s.ctx.resources.current('target','hp')==0 and not s.ctx.alive('target')
    # The old NoSource ledger has no opt-in provenance tag or action tasks.
    assert not any(e['type'].startswith('depletion.') for e in s.session.events)
    assert not any(t['kind']=='domain.depletion.action' for t in s.session.scheduler.pending)
    for e in s.session.events:
        if e['type']=='resource.changed':assert 'operation' not in e['payload']
    restored=Engine.restore(s.program,cp(s),providers=base.registry());assert cp(restored)==cp(s)

def main():
    guard=implementation_digest();results=[]
    for name,fn in [('custom_provider_under_graph_source_owner_nonzero_clock_override_cpp_public_head',custom_context_clock_cpp_head),('ordinary_no_optin_nosource_death_ledger_and_cpp_compatibility',legacy_no_optin)]:
        try:fn();results.append({'case':name,'passed':True})
        except Exception as error:results.append({'case':name,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    report={'core_before':guard,'core_after':implementation_digest(),'source_guard_equal':guard==implementation_digest(),'actual_exit':0 if all(x['passed'] for x in results) else 1,'results':results,'provider_observations':OBS}
    (OUT/'author.context.v2.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
