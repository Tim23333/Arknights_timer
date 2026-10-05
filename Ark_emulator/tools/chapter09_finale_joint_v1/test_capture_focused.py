import sys,json,copy,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_finale_joint_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
def fixture(refresh='retain'):
    return {'schemaVersion':2,'buffs':[{'id':'buff/sample','kind':'buff','duration_seconds':25,'capture':{'rule':'rule/sample','refresh':refresh,'parameters':{'offset':-.4}}}],'rules':[{'id':'rule/sample','kind':'rule','contract':'buff.capture','implementation':{'type':'expression','expression':"{'hp_ratio': inputs.target.components.resources.hp.current / inputs.target.components.resources.hp.spec.capacity + inputs.parameters.offset}"}}],'entities':[{'id':'unit/sample','kind':'entity','dependencies':['buff/sample'],'components':{'attributes':{'base':{'max_hp':50000}},'resources':{'hp':{'role':'health','initial':50000,'capacity':50000}},'spatial':{}}}],'scenarioDraft':{'id':'scene/sample','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/sample','instanceAlias':'source','position':{'row':0,'col':0}}]}}
def sim(p=None):return Engine.create(Compiler().compile(p or fixture()))
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def inst(s):return s.ctx.get('source',('buffs','instances'))[0]
def cases():
    for hp in [40000,35000,25000]:
        s=sim();s.ctx.resources.adjust('source','hp',value=hp);s.ctx.buffs.apply('source','source','buff/sample');assert abs(inst(s)['blackboard']['hp_ratio']-(hp/50000-.4))<1e-12
        r=Engine.restore(s.program,cp(s));s.session.advance(100);r.session.advance(100);assert cp(s)==cp(r)
    for refresh,expected in [('retain',.4),('resample',.1)]:
        s=sim(fixture(refresh));s.ctx.resources.adjust('source','hp',value=40000);s.ctx.buffs.apply('source','source','buff/sample');s.session.advance(3);s.ctx.resources.adjust('source','hp',value=25000);s.ctx.buffs.apply('source','source','buff/sample');assert abs(inst(s)['blackboard']['hp_ratio']-expected)<1e-12;assert cp(Engine.restore(s.program,cp(s)))==cp(s)
    s=sim();s.ctx.resources.adjust('source','hp',value=40000);s.ctx.buffs.apply('source','source','buff/sample');original=cp(s)
    for field in ['blackboard','capture','event','stamp','time']:
        bad=copy.deepcopy(original);buff=next(e for e in bad['kernel']['world']['entities'] if e['definition_id']=='unit/sample')['components']['buffs']['instances'][0]
        if field=='blackboard':buff['blackboard']['hp_ratio']=.99
        elif field=='capture':buff.pop('capture')
        elif field=='event':buff['capture']['sample_event']=1
        elif field=='stamp':buff['capture']['target_stamp']['life']=9
        else:buff['capture']['sample_time']=3
        try:Engine.restore(s.program,bad)
        except (ValueError,KeyError):pass
        else:raise AssertionError('tampered '+field+' restored')
    p=fixture();p['rules'][0]['implementation']['expression']="{'bad': 1e309}";s=sim(p);before=cp(s)
    try:s.ctx.buffs.apply('source','source','buff/sample')
    except ValueError:pass
    else:raise AssertionError('nonfinite capture accepted')
    assert cp(s)==before
    p=fixture();p['buffs'][0]['effects']=[{'op':'random','stream':'capture_fault','probability':1,'on_success':[{'op':'modify_resource','resource':'missing','amount':1}]}];s=sim(p);before=cp(s)
    try:s.ctx.buffs.apply('source','source','buff/sample')
    except ValueError:pass
    else:raise AssertionError('capture late effect fault accepted')
    assert cp(s)==before
    s=sim();s.ctx.buffs.apply('source','source','buff/sample');old=copy.deepcopy(inst(s));s.ctx.buffs.remove('source','buff/sample');bad=cp(s);entity=next(e for e in bad['kernel']['world']['entities'] if e['definition_id']=='unit/sample');entity['components']['buffs']['instances']=[old]
    try:Engine.restore(s.program,bad)
    except ValueError:pass
    else:raise AssertionError('removed memory reactivated')
    def mutator(inputs,params,context):
        active[0].ctx.session.random.sample('bad_capture');return {'hp_ratio':1}
    p=fixture();p['rules'][0]['implementation']={'type':'provider','provider':'test/mutator'};providers={'test/mutator':{'callable':mutator,'version':'1'}}
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    providers={**BUILTIN_PROVIDERS,**providers};active=[Engine.create(Compiler(providers=providers).compile(p),providers=providers)];s=active[0];before=cp(s)
    try:s.ctx.buffs.apply('source','source','buff/sample')
    except (RuntimeError,ValueError):pass
    else:raise AssertionError('pure provider wrote RNG')
    assert cp(s)==before
def main():
    before=implementation_digest()
    try:cases();result={'passed':True};code=0
    except Exception as error:result={'passed':False,'error':str(error),'traceback':traceback.format_exc()};code=1
    r={'core_before':before,'core_after':implementation_digest(),'actual_exit':code,'result':result};(ROOT/'validation/campaign/chapter09_finale_joint_v1/capture.focused.v1.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r));return code
if __name__=='__main__':raise SystemExit(main())
