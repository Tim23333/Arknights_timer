"""Independent source business oracle, never imports author test fixtures."""
import argparse,copy,hashlib,json,os,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
 freeze=ROOT/'validation/campaign/chapter10_dmech_source_v1/freeze.source.v1.json';assert sha(freeze)=='cec0698e0e57341b0e78b2f7ff3f3124d9248eabdb3922005718db9f1f26e84e';f=json.loads(freeze.read_bytes());runtime=Path(f['candidate']);sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.contracts import thaw
 from ark_sim.tools.replay import replay
 from tools.chapter10_dmech_source_v1 import build as source
 assert implementation_digest()==f['core'];assert all(sha(p)==h for p,h in f['locks'].items());providers=source.providers();log=Path(os.environ['ARKSIM_RUN_DIR']);facts={};results=[]
 def actor(id,tags,hp,sp=None,abilities=()):
  resources={'hp':{'role':'health','initial':hp,'capacity':hp}}
  if sp is not None:resources['sp']={'initial':sp,'capacity':127}
  return {'id':id,'kind':'entity','tags':tags,'components':{'attributes':{'base':{'max_hp':hp,'atk':9876,'def':0,'mres':0,'block_count':0}},'resources':resources,'selection_state':{'side':0,'motion':1,'category':2 if sp is not None else 1,'unit_type':1},'spatial':{},'abilities':list(abilities)}}
 def package(mode=None):
  module=source.build();definitions=[]
  for key in ['entities','abilities','buffs','rules','selectors','projectiles','definitions']:definitions.extend(copy.deepcopy(module.get(key,[])))
  definitions.extend([actor('unit/peer/cannon',['gunctrl'],7777,46),actor('unit/peer/hitter',['player'],8888,abilities=['ability/peer/control','ability/peer/kill']),{'id':'selector/peer/dmech','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy_1223_dmech'},{'state':'alive'}],'limit':1},{'id':'buff/peer/silence','kind':'buff','duration_seconds':5,'selection_flags':{'abnormal_flags':[12]}},{'id':'buff/peer/stun','kind':'buff','duration_seconds':5,'selection_flags':{'abnormal_flags':[0]},'control':{'can_move':False,'can_attack':False,'can_cast':False,'interrupt':True}},{'id':'ability/peer/control','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/dmech','timeline':[{'at':0,'effect':{'op':'apply_buff','target':'selected','buff':'buff/peer/'+('stun' if mode=='stun' else 'silence')}}]},{'id':'ability/peer/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/dmech','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}])
  p={'schemaVersion':2,'definitions':definitions,'scenarioDraft':{'id':'scene/peer/dmech','ruleset':'ruleset/ark_standard','map':{'rows':4,'cols':7},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':source.BODY,'instanceAlias':'artisan','position':{'row':1,'col':0}},{'definition':'unit/peer/cannon','instanceAlias':'cannon','position':{'row':2,'col':5}},{'definition':'unit/peer/hitter','instanceAlias':'hitter','position':{'row':3,'col':0}}],'commands':[]}}
  if mode in ['stun','silence']:p['scenarioDraft']['commands']=[{'at':220,'action':'skill','source':'hitter','ability':'ability/peer/control'}]
  if mode=='death':p['scenarioDraft']['commands']=[{'at':215,'action':'skill','source':'hitter','ability':'ability/peer/kill'}]
  source.bind_status_definitions(p);return p
 def cp(s):return json.loads(json.dumps(s.checkpoint()))
 def create(p):return Engine.create(Compiler(providers=providers).compile(p),providers=providers,seed=619)
 def value(s):return s.ctx.resources.current('cannon','sp')
 def full(p,label,at,end):
  s=create(p);s.advance(at);path=log/(label+'.checkpoint.json');path.write_text(json.dumps(cp(s)),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=providers);assert cp(s)==cp(r);s.advance(end-at);r.advance(end-at);h=replay(s.program,s.export_replay(),providers=providers);assert cp(s)==cp(r)==cp(h);facts[label]={'full_CP_head_equal':True,'checkpoint_sha':sha(path),'program':s.program.fingerprint,'cannonSP':value(s),'attachments':thaw(s.ctx.attachments.state()),'events':[thaw(e) for e in s.session.events if e['type'] in ['ability.started','ability.finished','ability.interrupted','buff.owned_interrupt.complete','descendant.born','descendant.issued','command.accepted','command.rejected']]};return s
 def native_full():
  s=full(package(),'full',200,830);instances=list(s.ctx.attachments.state()['instances'].values());assert len(instances)==1;link=instances[0];assert link['packets']==20 and link['reason']=='complete' and value(s)==66;assert s.ctx.resources.current('artisan','native_skill_uses')==0 and s.ctx.resources.current('artisan','hp')==6000;facts['full']['link_clock']=thaw(link)
  assert not s.ctx.get('artisan',('buffs','instances'));assert len([e for e in s.session.events if e['type']=='ability.started' and e['payload'].get('ability')==source.CHARGE])==1
 def silence():
  s=full(package('silence'),'silence',210,270);x=next(iter(s.ctx.attachments.state()['instances'].values()));assert x['packets']==2 and value(s)==33 and x['reason']=='source_flags';assert not any(e['type']=='ability.interrupted' and e['payload'].get('ability')==source.CHARGE for e in s.session.events);assert not s.ctx.get('artisan',('buffs','instances'))
 def stun():
  s=full(package('stun'),'stun',210,270);x=next(iter(s.ctx.attachments.state()['instances'].values()));assert x['packets']==2 and value(s)==33;callbacks=[e for e in s.session.events if e['type']=='buff.owned_interrupt.complete'];assert len(callbacks)==1;assert s.ctx.resources.current('artisan','hp')==6000
 def death():
  s=full(package('death'),'death',210,270);assert s.ctx.resources.current('artisan','hp')==0 and value(s)==33;children=[thaw(e) for e in s.session.events if e['type']=='descendant.born'];facts['death']['born']=children;assert len(children)==1 and children[0]['time']==245;assert len([e for e in s.session.events if e['type']=='buff.owned_interrupt.complete'])==1
 def selector_invalid():
  for kind in ['category','tag','neutral']:
   p=package();target=next(x for x in p['definitions'] if x['id']=='unit/peer/cannon')
   if kind=='category':target['components']['selection_state']['category']=1
   if kind=='tag':target['tags']=[]
   if kind=='neutral':target['components']['selection_state']['side']=2
   s=full(p,'invalid_'+kind,151,190);assert value(s)==46 and s.ctx.resources.current('artisan','sp')==5 and s.ctx.resources.current('artisan','native_skill_uses')==1 and not s.ctx.attachments.state()['instances']
 guards={str(p):sha(p) for p in [freeze,Path(__file__),Path(source.__file__)]+[Path(p) for p in f['locks']]+[p for p in (runtime/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]}
 for fn in [native_full,silence,stun,death,selector_invalid]:
  try:fn();results.append({'case':fn.__name__,'passed':True})
  except Exception as e:results.append({'case':fn.__name__,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
 after={p:sha(p) for p in guards};code=0 if all(x['passed'] for x in results) and guards==after else 1;report={'schema':'ark-sim/dmech-source-independent-peer/v1','core':implementation_digest(),'actual_exit':code,'results':results,'facts':facts,'source_before':guards,'source_after':after,'source_equal':guards==after,'comparison_exclusions':[],'whole_or_client_approved':False};assert not args.output.exists();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
