import sys,json,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_mandra_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
def fixture():
    return {'schemaVersion':2,'rules':[{'id':'rule/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity'}}],'behaviors':[{'id':'behavior/modes','kind':'behavior','initial':'mode0','states':{'mode0':{},'mode2':{}},'transitions':[]}],'entities':[{'id':'unit/modes','kind':'entity','components':{'attributes':{'base':{'max_hp':50000}},'resources':{'hp':{'role':'health','initial':50000,'capacity':50000}},'spatial':{},'behavior':{'machine':'behavior/modes'},'lifecycle':{'policy':'policy/ark_lifecycle'},'rebirth':{'resource':'hp','max_count':1,'delay_seconds':5,'restore_ratio':1,'restore_rule':'rule/restore','on_begin':[{'op':'transition','state':'mode2'}]}}}],'scenarioDraft':{'id':'scene/waiting-mode','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'initialEntities':[{'definition':'unit/modes','instanceAlias':'source','position':{'row':0,'col':0}}]}}
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def run():
    s=Engine.create(Compiler().compile(fixture()));s.ctx.resources.adjust('source','hp',value=0);assert s.ctx.get('source',('behavior','state'))=='mode2' and s.ctx.resources.current('source','hp')==0 and not s.ctx.active('source')
    before=cp(s)
    try:s.ctx.behavior.transition('source','mode0')
    except ValueError:pass
    else:raise AssertionError('ordinary waiting mode write accepted')
    assert cp(s)==before
    s.ctx.effects.execute('source',['source'],{'op':'transition','state':'mode0'},cast={'rebirth':{'target':s.session.world.resolve('source'),'generation':1,'phase':'waiting'}});assert s.ctx.get('source',('behavior','state'))=='mode2'
    r=Engine.restore(s.program,cp(s));s.advance(151);r.advance(151);assert cp(s)==cp(r) and s.ctx.resources.current('source','hp')==50000
def main():
    guard=implementation_digest()
    try:run();code=0;result={'passed':True}
    except Exception as error:code=1;result={'passed':False,'error':str(error),'traceback':traceback.format_exc()}
    report={'core_before':guard,'core_after':implementation_digest(),'actual_exit':code,'result':result};(ROOT/'validation/campaign/chapter09_mandra_v1/author.waiting_mode.final.v2.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report));return code
if __name__=='__main__':raise SystemExit(main())
