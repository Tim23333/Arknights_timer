import sys,os,json,hashlib,traceback,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_owned_interrupt_callbacks_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter10_dmech_source_v1 import build as source
from tools.chapter10_gunctrl_v3 import build as gun
from tools.chapter10_gunctrl_v1 import build as gun1
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/chapter10_dmech_source_v1';FACT={};RESULT=[];CP=[];REG={**source.providers(),**gun.providers()}
CORE='da218736ae42600b5d80653b411508b13438e9002b18af3f04233285ac3cb226'
def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*list((CAND/'ark_sim').rglob('*.py')),*list((CAND/'ark_sim').rglob('*.json')),Path(source.__file__),Path(gun.__file__),source.SOURCE,source.BSON] if 'validation' not in p.parts}
def package(control=None):
    a=source.build();b=gun.build();defs={}
    for p in [a,b]:
        for field in ['definitions','entities','abilities','buffs','selectors','rules','projectiles']:
            for d in p.get(field,[]):
                if d['id'] in defs:assert defs[d['id']]==d
                defs[d['id']]=copy.deepcopy(d)
    p={'schemaVersion':2,'definitions':list(defs.values())}
    next(x for x in p['definitions'] if x['id']==gun1.SHOT)['activation']['condition']='False'
    cannon=defs[gun1.BODY];cannon['components']['resources']['sp'].update(initial=31,recovery_rate=0)
    # p contains copied rows, so update the actual declared test copy.
    next(x for x in p['definitions'] if x['id']==gun1.BODY)['components']['resources']['sp'].update(initial=31,recovery_rate=0)
    initial=[{'definition':source.BODY,'instanceAlias':'dmech','position':{'row':2,'col':1}},{'definition':gun1.BODY,'instanceAlias':'cannon','position':{'row':2,'col':3}}];commands=[]
    if control:
        flag={'silence':12,'stun':0,'freeze':16}[control];bid='buff/test/dmech/'+control
        p['definitions'] += [{'id':bid,'kind':'buff','duration_seconds':2,'selection_flags':{'abnormal_flags':[flag]},'control':{'abilities':False,'attack':False,'move':False,'interrupt':control!='silence'}},{'id':'selector/test/dmech','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy_1223_dmech'}],'limit':1},{'id':'ability/test/control','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/dmech','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':bid}}]},{'id':'unit/test/controller','kind':'entity','components':{'attributes':{'base':{'max_hp':17777,'atk':817,'def':683,'mres':39}},'resources':{'hp':{'role':'health','initial':17777,'capacity':17777}},'spatial':{},'abilities':['ability/test/control'],'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1}}}]
        initial.append({'definition':'unit/test/controller','instanceAlias':'controller','position':{'row':0,'col':0}});commands.append({'at':220,'action':'skill','source':'controller','ability':'ability/test/control'})
    source.bind_status_definitions(p);gun1.bind_status_definitions(p)
    p['scenarioDraft']={'id':'scene/dmech/'+str(control),'ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':6},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':initial,'commands':commands}
    return p
def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=1777381)
def facts(s):return {'SP':s.ctx.resources.current('cannon','sp'),'sourceSP':s.ctx.resources.current('dmech','sp'),'uses':s.ctx.resources.current('dmech','native_skill_uses'),'attachments':thaw(s.ctx.attachments.state()),'events':[thaw(e) for e in s.session.events if e['type'] in ['attachment.started','attachment.reached','attachment.finished','ability.started','ability.finished','ability.interrupted','resource.modified','resource.adjusted','resource.paid']]}
def cpp(p,end,label):
    a=create(p);a.advance(end);b=create(p)
    for t in [180,230,500]:
        if t>=end:continue
        b.advance(t-b.session.time);path=LOG/(label+str(t)+'.checkpoint.json');h=write_ordered(path,b.checkpoint());CP.append({'path':str(path),'sha256':h,'bytes':path.stat().st_size});before=b.checkpoint();b=Engine.restore(b.program,load_bound(path,h),providers=REG);assert b.checkpoint()==before
    b.advance(end-b.session.time);head=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==head.checkpoint();assert list(a.session.events)==list(b.session.events)==list(head.session.events);return a
def finite():
    s=cpp(package(),900,'finite');FACT['finite']=facts(s);x=next(iter(s.ctx.attachments.state()['instances'].values()));assert x['packets']==20 and x['reason']=='complete';assert s.ctx.resources.current('cannon','sp')==51;assert s.ctx.resources.current('dmech','native_skill_uses')==0
    casts=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==source.CHARGE];assert len(casts)==1
    reached=next(e for e in s.session.events if e['type']=='attachment.reached');assert x['held_until']-reached['time']==600
    FACT['finite']['cooldown']=s.ctx.get('dmech',('runtime','cooldowns'),{})
def control(which):
    s=cpp(package(which),420,which);FACT[which]=facts(s);x=next(iter(s.ctx.attachments.state()['instances'].values()));assert not x['active'];assert s.ctx.resources.current('cannon','sp')==31+x['packets']-15;assert s.ctx.resources.current('dmech','native_skill_uses')==0

try:
 BEFORE=guard();p=package('stun');owned=next(b for b in p['definitions'] if b['id']==source.OWN);next(e for e in owned['events'] if e['event']=='ability.interrupted')['owned_callback']={'mode':'synchronous_interrupt','ability':source.CHARGE,'allow_owner_inactive':True};p['scenarioDraft']['commands'][0]['at']=215;ability=next(a for a in p['definitions'] if a['id']=='ability/test/control');next(e for e in p['definitions'] if e['id']=='unit/test/controller')['components']['attributes']['base']['atk']=10000;ability['timeline'][0]['effect']={'op':'damage','damage_type':'true','scale':1};s=create(p);s.advance(214);
 from ark_sim.domains.owned_interrupt_callbacks import capture
 sid=s.session.world.resolve('dmech');cs=next(iter(s.ctx.get(sid,('runtime','casts'),{}).values()));preview={'enabled':s.ctx.abilities._owned_interrupt_enabled,'definition':thaw(s.program.definitions[source.OWN]),'instances':s.ctx.get(sid,('buffs','instances'),[]),'captures':capture(s.ctx.abilities,sid,cs,'dead')};(ROOT/'validation/campaign/campaign_owned_interrupt_callbacks_v1/capture.preview.v1.json').write_text(json.dumps(preview,indent=2),encoding='utf8');s.advance(37);f=facts(s);f['source_state']=thaw(s.ctx.entity('dmech'));f['children']=[thaw(e) for e in s.session.world.entities() if e['definition_id']=='unit/ch10/bloodline/enemy_1220_dzoms'];f['native_death_events']=[thaw(e) for e in s.session.events if e['type'].startswith(('descendant.','ability.','entity.','buff.'))];f['death_interrupted_expected_sp']=31+next(iter(s.ctx.attachments.state()['instances'].values()))['packets']-15;r={'core':implementation_digest(),'actual_exit':0,'facts':f,'source_before':BEFORE,'source_after':guard(),'source_guard_equal':BEFORE==guard(),'scope':'Actual public lethal during owned link; native ON_ABILITY_INTERRUPTED and delayed1s child proof; prior blanket source interrupt expectation is assessed, not silently weakened.'};(ROOT/'validation/campaign/campaign_owned_interrupt_callbacks_v1/author.death.preview.v3.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps({'SP':f['SP'],'expected':f['death_interrupted_expected_sp'],'children':len(f['children'])}))
except Exception:
 r={'actual_exit':1,'traceback':traceback.format_exc()};(ROOT/'validation/campaign/campaign_owned_interrupt_callbacks_v1/author.death.preview.failure.v3.json').write_text(json.dumps(r,indent=2),encoding='utf8');raise
