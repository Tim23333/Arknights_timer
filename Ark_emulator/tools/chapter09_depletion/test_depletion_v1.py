"""Bounded exact-zero primitive proof; tile-cast collapse bridge remains pending."""
import sys,json,copy,hashlib,subprocess,os,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_depletion_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.contracts import digest
from ark_sim.tools.replay import replay
OUT=ROOT/'validation/campaign/chapter09_depletion';LOG=Path('E:/ArkSimLogs/runs/chapter09_depletion_author_v1');RESULTS=[];ARTIFACTS=[];CLEANUPS=[]
def policy(inputs,params,context):
    stage=inputs['state']['stage'];req=inputs['request']
    if stage=='normal':return {'action':'defer','stage':'damaged','actions':['begin','ready']}
    return {'action':'none','stage':stage,'actions':[]}
def registry():return {**BUILTIN_PROVIDERS,'reference/depletion/plan':{'callable':policy,'version':'1'}}
def data(*,fault=False):
    target={'attributes':{'base':{'max_hp':50,'atk':12000,'def':0,'mres':0}},'resources':{'hp':{'role':'health','initial':50,'capacity':50}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'depletion':{'resource':'hp','rule':'rule/depletion/plan','initial_stage':'normal','parameters':{},'stages':{'normal':{'active':True,'selectable':True},'damaged':{'active':False,'selectable':False},'ready':{'active':True,'selectable':True}},'actions':{'begin':{'at_seconds':0,'effects':[{'op':'apply_buff','buff':'buff/depletion/startdead'}]},'ready':{'at_seconds':2,'next_stage':'ready','effects':[{'op':'remove_buff','buff':'buff/depletion/startdead'},{'op':'apply_buff','buff':'buff/depletion/candead'}]}}}}
    if fault:target['depletion']['actions']['begin']['effects']+=[{'op':'random','stream':'fault','probability':1,'on_success':[{'op':'modify_resource','resource':'missing','amount':1}]}]
    d={'schemaVersion':2,'entities':[{'id':'unit/depletion/source','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':100,'atk':60,'def':0,'mres':0}},'resources':{'hp':{'role':'health','initial':100,'capacity':100}},'spatial':{},'abilities':['ability/depletion/hit']}},{'id':'unit/depletion/target','kind':'entity','tags':['pillar'],'components':target}],'rules':[{'id':'rule/depletion/plan','kind':'rule','contract':'resource.depletion','implementation':{'type':'provider','provider':'reference/depletion/plan'}}],'buffs':[{'id':'buff/depletion/startdead','kind':'buff','selection_flags':{'abnormal_flags':[5,2,15]}},{'id':'buff/depletion/candead','kind':'buff'}],'selectors':[{'id':'selector/depletion/target','kind':'selector','region':{'type':'all'},'filters':[{'tag':'pillar'},{'state':'alive'}],'limit':1}],'abilities':[{'id':'ability/depletion/hit','kind':'ability','activation':{'mode':'manual'},'selector':'selector/depletion/target','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}],'scenarioDraft':{'id':'scene/depletion','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':4},'initialEntities':[{'definition':'unit/depletion/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/depletion/target','instanceAlias':'target','position':{'row':0,'col':1}}]}}
    return d
def sim(d=None):return Engine.create(Compiler(providers=registry()).compile(d or data()),providers=registry(),seed=901)
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def zero(s):s.ctx.effects.execute('source',['target'],{'op':'damage','damage_type':'true','scale':1})
def cleanup():
    if LOG.exists() and any(LOG.glob('*.json')):
        r=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs_v2.py'),'--run-dir',str(LOG),'--apply','--minimum-age-minutes','0','--completed-pid',str(os.getpid())],capture_output=True,text=True,encoding='utf8',check=True);CLEANUPS.append(json.loads(r.stdout))
def case(name,fn):
    try:fn();RESULTS.append({'case':name,'passed':True})
    except Exception as e:RESULTS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    finally:cleanup()
def exact_zero_ready_source():
    s=sim();zero(s);state=s.ctx.depletion.state('target');assert s.ctx.resources.current('target','hp')==0 and s.ctx.alive('target') and not s.ctx.active('target') and not s.ctx.effect_target_available('target')
    req=state['lease']['provenance'];assert req['operation']=='damage' and req['source']==s.session.world.resolve('source') and req['health_before']==50 and req['health_after']==0 and req['actual_health_loss']==50 and req['requested_change']==-60 and req['source_snapshot']['components']['spatial']['position']['col']==0
    s.session.advance(60);assert s.ctx.depletion.state('target')['stage']=='damaged';s.session.advance(1);assert s.ctx.depletion.state('target')['stage']=='ready' and s.ctx.resources.current('target','hp')==0 and s.ctx.alive('target');assert any(x['definition']=='buff/depletion/candead' for x in s.ctx.buffs._instances(s.session.world.resolve('target')))
def forged_callbacks_and_secondary_damage():
    s=sim();zero(s);before=cp(s);owner=s.session.world.resolve('target');s.ctx.depletion.action(s.session,{'target':owner,'generation':1,'slot':1});assert cp(s)==before
    try:s.ctx.effects.execute(owner,[owner],{'op':'emit','event':'forged'},cast={'depletion_action':{'owner':owner,'generation':1,'slot':'1'}})
    except ValueError:pass
    else:raise AssertionError('forged callback cast accepted')
    assert cp(s)==before;zero(s);assert s.ctx.resources.current('target','hp')==0 and s.ctx.depletion.state('target')['generation']==1
    s.session.schedule('domain.depletion.action',{'target':owner,'generation':1,'slot':1},0,phase=s.ctx.effect_phase);s.session.advance(1);assert s.ctx.depletion.state('target')['stage']=='damaged'
    try:s.ctx.resources.adjust(owner,'hp',value=1)
    except ValueError:pass
    else:raise AssertionError('positive HP workaround accepted')
def atomic_late_fault():
    s=sim(data(fault=True));before=cp(s)
    try:zero(s)
    except ValueError:pass
    else:raise AssertionError('missing-resource late fault absent')
    assert cp(s)==before and not s.ctx.depletion._callbacks and not s.ctx.depletion._attacks and not s.ctx.depletion._deliveries
def retire_cancels():
    s=sim();zero(s);s.ctx.lifecycle.retire('target','withdrawn');s.session.advance(65);assert not s.ctx.alive('target') and s.ctx.depletion.state('target')['lease'] is None and not [e for e in s.session.events if e['type']=='depletion.action.executed' and e['payload']['slot']=='1']
def cpp_head_tamper():
    d=data();d['scenarioDraft']['commands']=[{'at':0,'action':'skill','source':'source','ability':'ability/depletion/hit'}];s=sim(d);s.session.advance(1);LOG.mkdir(parents=True,exist_ok=True);path=LOG/'public.checkpoint.json';path.write_text(json.dumps(s.checkpoint()),encoding='utf8');checkpoint=json.loads(path.read_bytes());r=Engine.restore(s.program,checkpoint,providers=registry());s.session.advance(65);r.session.advance(65);assert s.checkpoint()==r.checkpoint();h=replay(s.program,s.export_replay(),providers=registry());assert h.checkpoint()==s.checkpoint()
    altered=copy.deepcopy(checkpoint);entity=next(x for x in altered['kernel']['world']['entities'] if x['definition_id']=='unit/depletion/target');entity['components']['runtime']['depletion']['lease']['actions']['1']['seq']+=1
    try:Engine.restore(s.program,altered,providers=registry())
    except ValueError:pass
    else:raise AssertionError('tampered task sequence restored')
    ARTIFACTS.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'cpp_equal':True,'public_replay_equal':True,'head_sha256':digest(s.checkpoint())})
def resource_not_attack_and_nested_authority():
    s=sim();s.ctx.resources.adjust('target','hp',value=0,source='source');assert s.ctx.depletion.state('target')['lease']['provenance']['operation']=='resource_change'
    s=sim();ref=s.session.world.resolve('target');effect={'op':'damage','damage_type':'true','scale':1}
    # Real attack frame of one actor/target/resource cannot bless a nested raw
    # resource change, even with identical values or misleading event metadata.
    with s.ctx.depletion.attack('source',ref,effect):s.ctx.resources.adjust(ref,'hp',value=0,source='source')
    assert s.ctx.depletion.state(ref)['lease']['provenance']['operation']=='resource_change'
def main():
    guard=implementation_digest()
    for name,fn in [('actual_exact_zero_source_and_two_second_candead',exact_zero_ready_source),('forged_direct_task_cast_secondary_zero_and_no_hp1',forged_callbacks_and_secondary_damage),('late_callback_fault_world_rng_jobs_health_rollback',atomic_late_fault),('retire_cancels_owned_due',retire_cancels),('public_cpp_head_and_task_tamper_rejected',cpp_head_tamper),('raw_resource_nested_scope_not_damage_authority',resource_not_attack_and_nested_authority)]:case(name,fn)
    report={'core':implementation_digest(),'source_guard_equal':guard==implementation_digest(),'actual_exit':0 if all(r['passed'] for r in RESULTS) else 1,'results':RESULTS,'artifacts':ARTIFACTS,'cleanup':CLEANUPS,'raw_deleted':all(not Path(x['path']).exists() for x in ARTIFACTS),'scope':'Bounded generic exact-zero defer/ready primitive, not full pillar collapse or duspfr payload','pending':['source pillar direction/collapse and tile-target owned-cast bridge','duspfr source-owned finite 3s/5-parallel payload','broader predefines source modifier policy']};OUT.mkdir(parents=True,exist_ok=True);(OUT/'author.primitive.v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
