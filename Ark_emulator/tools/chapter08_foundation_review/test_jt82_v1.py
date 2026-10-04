import sys,json,hashlib
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
STAGE=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v7.json';OVERLAY=STAGE.with_name('level_main_08-16.native_draft.v7.life99999.v1.json');OUT=ROOT/'validation/campaign/chapter08_jt82_v7_independent'
def providers():
 from tools.chapter08_buff_lifetime.talula_providers_v1 import providers as boss
 from tools.chapter08_special.policies_v2 import providers as special
 from tools.chapter08_ranged.policies_v1 import providers as ranged
 from tools.chapter08_environment.policies_v1 import providers as infection
 return {**boss(),**special(),**ranged(),**infection()}
def load():return json.loads(STAGE.read_bytes())
def exact(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return list(a)==list(b) and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 return a==b
def proof(p,name,split,end):
 reg=providers();pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg,seed=p['scenarioDraft']['seed']);s.advance(split);d=OUT/name;d.mkdir(parents=True,exist_ok=True);f=d/'checkpoint.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h),providers=reg);s.advance(end-split);r.advance(end-split);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=reg).checkpoint();(d/'evidence.json').write_text(json.dumps({'input':p,'cp_sha':h,'checkpoint':s.checkpoint()},indent=2),encoding='utf8');return s
def test_original_v7_source32_actions_options5variants_roster_allroutes_and_onlylife():
 p=load();assert hashlib.sha256(STAGE.read_bytes()).hexdigest()=='a7b061ea9bcb49f2bd6094a675d4840c224209a0ee645c9bbe32d32ad193146c';old=json.loads(STAGE.with_name('level_main_08-16.native_draft.v6.json').read_bytes());assert exact(p['definitions'],old['definitions']) and exact(p['scenarioDraft'],old['scenarioDraft']);src=json.loads((ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json').read_bytes());stage=src['stages']['level_main_08-16'];raw=stage['native_document'];scene=p['scenarioDraft'];assert scene['seed']==raw['randomSeed'];assert scene['parameters']['deploy_capacity']==9 and scene['resources']['dp']['initial']==10 and scene['resources']['life']=={'initial':3,'capacity':3};assert len(scene['roster'])==12 and scene['map']['tiles']==stage['map_plan']['tiles'];assert scene['metadata']['native_options']==raw['options'];count=0;used=0;control={}
 for w,nw in zip(scene['timeline']['waves'],raw['waves']):
  assert (w['pre_delay_seconds'],w['post_delay_seconds'],w['max_wait_seconds'])==(nw['preDelay'],nw['postDelay'],nw['maxTimeWaitingForNextWave']) and len(w['fragments'])==len(nw['fragments'])
  for f,nf in zip(w['fragments'],nw['fragments']):
   assert f['pre_delay_seconds']==nf['preDelay'] and len(f['actions'])==len(nf['actions'])
   for a,na in zip(f['actions'],nf['actions']):
    assert a['metadata']['native_action']==na and a['count']==na['count'] and a['delay_seconds']==na['preDelay'] and a['interval_seconds']==na['interval']
    if na['actionType']=='SPAWN':
     count+=na['count'];route=deepcopy(raw['routes'][na['routeIndex']]);height=scene['map']['rows'];route['startPosition']['row']=height-1-route['startPosition']['row'];route['endPosition']['row']=height-1-route['endPosition']['row']
     for ck in route.get('checkpoints') or []:ck['position']['row']=height-1-ck['position']['row']
     actual={k:v for k,v in a['spawn']['route'].items() if k not in ('transition_policy','reach_offset_policy')};assert exact(route,actual);used+=1
    else:control[na['actionType']]=control.get(na['actionType'],0)+na['count']
 assert count==32 and len(p['manifest']['metadata']['variant_bindings'])==5 and control=={'DISPLAY_ENEMY_INFO':1,'PREVIEW_CURSOR':1};q=json.loads(OVERLAY.read_bytes());q['scenarioDraft']['resources']['life']={'initial':3,'capacity':3}
 for new,base in [(q['manifest']['metadata'],p['manifest']['metadata']),(q['scenarioDraft']['metadata'],scene['metadata'])]:
  for k in set(new)-set(base):new.pop(k)
 assert exact(q,p)
def test_native_wholeplan_short180_CP47_no_source_births_cut_or_legacy_fixture_migration():
 p=load();s=proof(p,'original_wholeplan180',47,180);assert s.ctx.state()['pending_waves']>0;assert s.runtime_fingerprint==s.checkpoint()['runtime_fingerprint']
def test_current_nativeMap_infection_and_volcano_content_bindings_controlled400_CP113():
 p=load();scene=p['scenarioDraft'];scene.pop('timeline');scene.pop('branches',None);scene['objectives']={};scene['roster']=[];p['definitions'].append({'id':'unit/peer/jt82/probe','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':20000,'atk':120,'attack_speed_ratio':1,'def':317,'mres':81}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});scene['initialEntities'] += [{'definition':'unit/peer/jt82/probe','instanceAlias':'infected','position':{'row':4,'col':3}},{'definition':'unit/peer/jt82/probe','instanceAlias':'volcanic','position':{'row':4,'col':4}}];s=proof(p,'controlled_native_fields',113,400);assert s.ctx.attributes.values(s.session.world.resolve('infected'))['atk']==180;assert s.ctx.attributes.values(s.session.world.resolve('infected'))['attack_speed_ratio']==1.5;hp=s.ctx.resources.current('infected','hp');assert hp<20000;volcano=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['target']==s.session.world.resolve('volcanic')];assert volcano and all(e['payload']['amount']==1000 for e in volcano)
