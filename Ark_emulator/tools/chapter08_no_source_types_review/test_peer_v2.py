import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_no_source_types_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim.domains.providers import BUILTIN_PROVIDERS
OUT=ROOT/'validation/campaign/chapter08_no_source_types_independent_v2'
def pipeline(inputs,params,context):
 e=inputs['effect'];v=e['fixed_amount'];kind=e['damage_type']
 if kind=='physical':v=max(v*.05,v-e['target_def'])
 elif kind=='arts':v=max(v*.05,v*(1-e['target_res']/100))
 return {'accepted':True,'amount':v,'allocations':[],'events':[]}
def quarter(inputs,params,context):return {'accepted':True,'amount':inputs['effect']['settlement']['amount']*.25,'allocations':[],'events':[]}
REG={**BUILTIN_PROVIDERS,'peer.no_actor.pipeline':{'callable':pipeline,'version':'1'},'peer.target.quarter':{'callable':quarter,'version':'1'}}
def request(kind='arts',ignore=False,bypass=False,amount=1600):return {'op':'no_source_damage','fixed_amount':amount,'damage_type':kind,'attack_type':'BUFF','damage_without_modify':bypass,'ignore_for_sp':ignore,'node_is_env_damage':False,'env_blackboard_injected':False,'environmental':False,'origin':{'independent':'typed source None protocol'},'rules':{'damage.pipeline':'rule/peer/no_actor'}}
def package(kind='arts',ignore=False,bypass=False,hook=False,amount=1600):
 return {'schemaVersion':2,'manifest':{'id':'package/peer/no_actor','requires':['preset/ark_standard']},'entities':[{'id':'unit/peer/target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':8000,'atk':29,'def':913,'mres':65}},'resources':{'hp':{'initial':8000,'capacity':8000,'role':'health'},'sp':{'initial':0,'capacity':20,'recovery_rule':'rule/peer/spgain','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}},'spatial':{},'buffs':{'initial':['buff/peer/lower_res']+(['buff/peer/hook'] if hook else [])},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],'buffs':[{'id':'buff/peer/lower_res','kind':'buff','modifiers':[{'attribute':'mres','layer':'flat','value':-20}]},{'id':'buff/peer/hook','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/peer/quarter'}]}],'rules':[{'id':'rule/peer/spgain','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}},{'id':'rule/peer/no_actor','kind':'rule','contract':'damage.pipeline','metadata':{'input_bindings':{'target_def':{'entity':'target','attribute':'def'},'target_res':{'entity':'target','attribute':'mres'}}},'implementation':{'type':'provider','provider':'peer.no_actor.pipeline'}},{'id':'rule/peer/quarter','kind':'rule','contract':'damage.pipeline','implementation':{'type':'provider','provider':'peer.target.quarter'}}],'selectors':[{'id':'selector/peer/target','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}],'limit':1}],'scenarioDraft':{'id':'scene/peer/no_actor','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':3},'objectives':{},'initialEntities':[{'definition':'unit/peer/target','instanceAlias':'target','position':{'row':0,'col':1}}],'scheduledEffects':[{'at':13,'effect':dict(request(kind,ignore,bypass,amount),target=2)}]}}
def make(p):pr=Compiler(providers=REG).compile(p);return pr,Engine.create(pr,providers=REG,seed=82741)
def proof(p,pr,s,name,split=11,end=20):
 s.advance(split);path=Path('E:/ArkSimLogs/runs/no_source_types_peer_v2')/(name+'.json');path.parent.mkdir(parents=True,exist_ok=True);h=write_ordered(path,s.checkpoint());r=Engine.restore(pr,load_bound(path,h),providers=REG);s.advance(end-split);r.advance(end-split);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=REG).checkpoint();d=OUT/name;d.mkdir(parents=True,exist_ok=True);(d/'receipt.json').write_text(json.dumps({'cp_sha':h,'time':s.session.time,'events':len(s.session.events),'events_sha':hashlib.sha256(json.dumps(thaw(tuple(s.session.events))).encode()).hexdigest(),'checkpoint_and_head_equal':True,'raw_CP_cleaned':True},indent=2),encoding='utf8');path.unlink()
@pytest.mark.parametrize('kind,expected',[('arts',880),('physical',687),('true',1600)])
def test_actualNoneSource_differentliveTargetRES45_DEF913_damage_SP_CPP11_head(kind,expected):
 p=package(kind);pr,s=make(p);proof(p,pr,s,kind);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['payload']['source'] is None and hits[0]['payload']['amount']==expected;assert s.ctx.resources.current('target','hp')==8000-expected and s.ctx.resources.current('target','sp')==1;assert s.ctx.entity('target')['components']['attributes']['base']['mres']==65
@pytest.mark.parametrize('bypass,expected',[(False,220),(True,1600)])
def test_targetAfterHook_and_explicitbypass_keep_original_sourceNone_semantics(bypass,expected):
 p=package('arts',False,bypass,True);pr,s=make(p);proof(p,pr,s,'hook_'+str(bypass));assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[expected]
def test_ignoreSP_and_lethalHPbounds_oneNoneSourceClaim():
 p=package('true',True,amount=9999);pr,s=make(p);proof(p,pr,s,'lethal_ignore');assert s.ctx.resources.current('target','hp')==0 and not s.ctx.alive('target') and s.ctx.resources.current('target','sp')==0;claims=[e for e in s.session.events if e['type']=='combat.kill'];assert len(claims)==1 and claims[0]['payload']['source'] is None
def test_actor_source_or_cast_cannot_be_borrowed_including_inactive():
 p=package();p['scenarioDraft']['scheduledEffects']=[];pr,s=make(p);before=s.checkpoint()
 for source,cast in [('target',None),(None,{'id':'forged'})]:
  with pytest.raises(ValueError):s.ctx.effects.execute(source,[2],request(),cast=cast)
  assert s.checkpoint()==before
 s.ctx.set('target',('runtime','active'),False);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('target',[2],request())
 assert s.checkpoint()==before;s.ctx.effects.execute(None,[2],request());assert s.ctx.resources.current('target','hp')==8000
@pytest.mark.parametrize('key,value',[('fixed_amount',True),('damage_type',True),('attack_type',True),('damage_without_modify',1),('ignore_for_sp',1)])
def test_explicit_typed_request_invalid_never_partial(key,value):
 p=package();p['scenarioDraft']['scheduledEffects'][0]['effect'][key]=value
 with pytest.raises(Exception):Compiler(providers=REG).compile(p)
