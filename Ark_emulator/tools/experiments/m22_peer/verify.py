import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m21_integration_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
CORE='c069e0206c076b429750b3fd97a507c54fb8e34fee51376c2f979f434151b95e'
PINS={'01-11':'ad147b19e709d6dbd0f935c6a4aeb80e5f8dddad744af4ad0829f583cb8dc262','01-12':'a681a1d4fc76e613f658ea3a27fad4cd0ecd0923308f366b2dafe568af9f30ce'}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def data(level,npc=False):
 path=ROOT/f'packages/campaign/chapter01_stage_models/m22/level_main_{level}.partial.json';assert sha(path)==PINS[level];p=json.loads(path.read_bytes());uid='unit/ch1_predefined_adnach_e0_l20' if npc else 'unit/enemy_1028_mocock'+('_2' if level=='01-12' else '')
 ability='ability/ch1_predefined_adnach_normal' if npc else 'ability/enemy_1028_mocock'+('_2' if level=='01-12' else '')+'/ch1_model_normal'
 p['entities'].append({'id':'unit/target','kind':'entity','tags':['enemy' if npc else 'player','ground','primary'],'components':{'attributes':{'base':{'max_hp':4000,'def':30,'mres':0}},'resources':{'hp':{'initial':4000,'capacity':4000,'role':'health'}},'spatial':{},'abilities':['ability/move']}})
 p['abilities'].append({'id':'ability/move','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':3,'col':6}}]},'timeline':[]})
 p['scenarioDraft']={'id':'scenario/m22_independent','ruleset':'ruleset/ark_standard','roster':[],'map':{'rows':7,'cols':8},'resources':{'dp':{'initial':20,'capacity':99}},'objectives':{},'initialEntities':[{'definition':uid,'instanceAlias':'shooter','position':{'row':3,'col':3},'facing':'right'},{'definition':'unit/target','instanceAlias':'target','position':{'row':3,'col':4}}]}
 # Keep source actor definition/stat/attack unchanged; all other stage elements are uninstantiated.
 return p,uid,ability

def make(p):
 assert implementation_digest()==CORE;s=Engine.create(Compiler().compile(p),seed=2203);assert Path(sys.modules['ark_sim'].__file__).resolve().parent==RUNTIME/'ark_sim';return s

def ev(s,t):return [e for e in s.session.events if e['type']==t]
def finish(s,name,p,expected):
 cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();assert implementation_digest()==CORE
 return {'case':name,'fixture':p,'expected':expected,'program_fingerprint':s.program.fingerprint,'runtime_fingerprint':s.runtime_fingerprint,'commands':s.export_replay(),'checkpoint_equal':True,'replay_equal':True,'events':thaw([e for e in s.session.events if e['type'] in ('projectile.launched','projectile.hit','projectile.invalid','damage.accepted','command.accepted','buff.applied')])}

def run():
 results=[]
 for level,stats,damage in [('01-11',(1550,180,50,2.7),150),('01-12',(2000,250,85,2.2),220)]:
  p,uid,aid=data(level);unit=next(e for e in p['entities'] if e['id']==uid);b=unit['components']['attributes']['base'];assert (b['max_hp'],b['atk'],b['def'],b['attack_interval'])==stats
  s=make(p);s.advance(29);hits=[e for e in ev(s,'damage.accepted') if e['payload'].get('ability')==aid];assert len(hits)==1 and hits[0]['time']==28 and hits[0]['payload']['amount']==damage;assert [e['time'] for e in ev(s,'projectile.launched')]==[22];assert s.ctx.resources.current('target','hp')==4000-damage;results.append(finish(s,'variant_'+level,p,{'stats':stats,'launch22':True,'impact28':True,'damage':damage}))
 # Public target movement and a newly deployed nearby decoy must not replace capture.
 p,uid,aid=data('01-12');p['entities'].append({'id':'unit/decoy','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':4000,'def':30,'mres':0}},'resources':{'hp':{'initial':4000,'capacity':4000,'role':'health'}},'spatial':{},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0}}});p['scenarioDraft']['roster']=['unit/decoy'];s=make(p);s.submit({'action':'skill','source':'target','ability':'ability/move'},at=23);s.submit({'action':'deploy','entity':'unit/decoy','alias':'decoy','position':{'row':3,'col':4}},at=24);s.advance(41);hits=[e for e in ev(s,'damage.accepted') if e['payload'].get('ability')==aid];assert len(hits)==1 and hits[0]['time']==40 and hits[0]['payload']['target']==s.session.world.resolve('target');assert s.ctx.resources.current('decoy','hp')==4000;results.append(finish(s,'moving_capture_new_nearer_decoy',p,{'impact40':True,'no_retarget':True}))
 for who in ('shooter','target'):
  p,uid,aid=data('01-11');s=make(p);s.submit({'action':'withdraw','source':who},at=23);s.advance(31);hits=[e for e in ev(s,'damage.accepted') if e['payload'].get('ability')==aid];assert len(hits)==(1 if who=='shooter' else 0);assert ev(s,'command.accepted');results.append(finish(s,'retire_'+who,p,{'damage_packets':len(hits),'capture_invalid_no_retarget':True}))
 p,uid,aid=data('01-11',True);p['entities'].append({'id':'unit/director','kind':'entity','components':{'spatial':{},'abilities':['ability/grant']}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':0}});p['selectors'].append({'id':'selector/npc','kind':'selector','region':{'type':'all'},'filters':[{'tag':'predefined'},{'state':'alive'}],'limit':1});p['buffs'].append({'id':'buff/plus100','kind':'buff','duration_seconds':1,'modifiers':[{'attribute':'atk','layer':'flat','value':100}]});p['abilities'].append({'id':'ability/grant','kind':'ability','selector':'selector/npc','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/plus100'}]},'timeline':[]});s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/grant'},at=10);s.advance(14);hits=[e for e in ev(s,'damage.accepted') if e['payload'].get('ability')==aid];assert len(hits)==1 and hits[0]['time']==12 and hits[0]['payload']['amount']==269;results.append(finish(s,'NPC_live_at_hit_external_buff',p,{'launch9_impact12':True,'live299_minus30':269}))
 report={'schema':'ark-sim/m22-independent-ranged-review/v1','passed':True,'implementation_sha256':CORE,'runtime_module':sys.modules['ark_sim'].__file__,'target_content_pins':PINS,'cases':results,'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(__file__),'result':'passed'}],'formal_approval':False,'scope':'Six isolated actual compiled actors/abilities, no fullstage receipt/native body assertion'};out=ROOT/'validation/campaign/m22_peer/first_cases.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'cases':len(results),'core':CORE}))
if __name__=='__main__':run()
