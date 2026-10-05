"""Independent four corrected source MandraV2 gates; no author fixtures."""
import os,sys,json,hashlib,traceback
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_finale_joint_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter09_mandra_v2.build import providers,BODY,IMMUNE
CORE='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18';assert implementation_digest()==CORE
BASE=ROOT/'packages/campaign/chapter09_consumers/mandra_v2';FREEZE=ROOT/'validation/campaign/chapter09_mandra_v2/freeze.source.v2.json';OUT=ROOT/'validation/campaign/chapter09_mandra_peer_v2';LOG=Path(os.environ['ARKSIM_RUN_DIR']);REG=providers();HP=41737;SHIELD='buff/ch9/mandra/shield';AREA='buff/ch9/mandra/stone_area';INV='buff/ch9/mandra/invulnerable';RAY='ability/ch9/mandra/ray';SUMMON='ability/ch9/mandra/summon';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE;assert sha(FREEZE)=='98fb5c6676292f787cb0bad6fe3e1195545aa4a975dc27196c305685fdf56af5';f=json.loads(FREEZE.read_bytes());assert f['core_before']==f['core_after']==CORE
 for m in f['modules']:assert sha(ROOT/m['path'])==m['sha256']
 paths=[FREEZE,ROOT/'tools/chapter09_mandra_v2/build.py',BASE/'module.talent_prefix.v2.json',BASE/'module.skill_prefix.v2.json',BASE/'damage_resistance.source.v1.json',BASE/'source.reborn.callgraph.v2.json']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts];return {str(p):sha(p) for p in paths}
START=guard();OUT.mkdir(parents=True,exist_ok=True);RESULTS=[];FACTS={};ART=[]
def scene(profile='talent_prefix',near=False):
 p=json.loads((BASE/('module.'+profile+'.v2.json')).read_bytes());p['manifest']['requires']=['preset/ark_standard'];boss=next(e for e in p['entities'] if e['id']==BODY);boss['components']['attributes']['base'].update(max_hp=HP,atk=817,**{'def':683,'mres':39});boss['components']['resources']['hp'].update(initial=HP,capacity=HP);
 for ability in p['abilities']:
  if ability['id'] in boss['components']['abilities'] and ('/normal_' in ability['id'] or ability['id'] in [RAY,SUMMON]):ability['activation']['condition']='False'

 player={'id':'unit/peer/v2/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':34219,'atk':1400,'def':727,'mres':31,'attack_speed_ratio':1.2}},'resources':{'hp':{'initial':34219,'capacity':34219,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}};killer=deepcopy(player);killer['id']='unit/peer/v2/killer';killer['components']['attributes']['base']['atk']=100000;p['entities'] += [player,killer];p['selectors'].append({'id':'selector/peer/v2/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}],'limit':1})
 for kind in ['physical','arts','true']:
  aid='ability/peer/v2/'+kind;player['components']['abilities'].append(aid);p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/v2/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':kind,'scale':1}}]})
 killer['components']['abilities']=['ability/peer/v2/lethal'];p['abilities'].append({'id':'ability/peer/v2/lethal','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/v2/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
 p['scenarioDraft']={'id':'scene/peer/v2/'+profile,'ruleset':'ruleset/ark_standard','map':{'rows':11,'cols':12},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':BODY,'instanceAlias':'boss','position':{'row':4,'col':4}},{'definition':player['id'],'instanceAlias':'player','position':{'row':4,'col':5.6} if near else {'row':9,'col':8}},{'definition':killer['id'],'instanceAlias':'killer','position':{'row':9,'col':9}}],'commands':[]};return p

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=41737683)
def events(s,t):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==t]
def buffs(s):return s.ctx.get('boss',('buffs','instances'))
def proof(p,name,splits,end):
 a=create(p);a.advance(end);b=create(p);pins=[]
 for t in splits:
  b.advance(t-b.session.time);path=LOG/(name+str(t)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append({'path':str(path),'sha256':pin,'bytes':path.stat().st_size});b=Engine.restore(b.program,load_bound(path,pin),providers=REG)
 b.advance(end-b.session.time);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();ART.extend(pins);(OUT/(name+'.json')).write_text(json.dumps({'core':CORE,'actual_full_CPP_head_equal':True,'CPs':pins,'input_digest':digest(p)},indent=2),encoding='utf8');return a

def mask():
 p=scene();p['scenarioDraft']['commands']=[{'at':t,'action':'skill','source':'player','ability':'ability/peer/v2/'+kind} for t,kind in [(7,'physical'),(11,'arts'),(15,'true')]];s=proof(p,'mask_correct',[8,12],20);hits=events(s,'damage.accepted');assert [(t,x['ability']) for t,x in hits]==[(7,'ability/peer/v2/physical'),(11,'ability/peer/v2/arts'),(15,'ability/peer/v2/true')];assert all(abs(x['amount']-want)<1e-8 for (_,x),want in zip(hits,[286.8,341.6,1400]));assert abs(s.ctx.resources.current('boss','hp')-(HP-2028.4))<1e-8;FACTS['mask']={'physical1400_DEF683':286.8,'arts1400_RES39':341.6,'true1400':1400}

def restored_profiles():
 facts=[]
 for profile,inv,cd in [('talent_prefix',90,600),('skill_prefix',150,300)]:
  p=scene(profile,near=True);p['scenarioDraft']['commands']=[{'at':11,'action':'skill','source':'killer','ability':'ability/peer/v2/lethal'},{'at':170,'action':'skill','source':'player','ability':'ability/peer/v2/true'},{'at':162+inv,'action':'skill','source':'player','ability':'ability/peer/v2/physical'}];s=create(p);s.advance(12);assert s.ctx.resources.current('boss','hp')==0;assert {b['definition'] for b in buffs(s)}=={IMMUNE};s.advance(150);assert s.ctx.resources.current('boss','hp')==HP and s.ctx.get('boss',('behavior','state'))=='fly_stone';ids={b['definition'] for b in buffs(s)};assert {SHIELD,AREA,INV,IMMUNE}<=ids;ib=next(b for b in buffs(s) if b['definition']==INV);assert ib['started_at']==161 and ib['expires_at']==161+inv;assert s.ctx.get('boss',('runtime','cooldowns',RAY))==461;assert s.ctx.get('boss',('runtime','cooldowns',SUMMON))==161+cd;s=proof(p,'restore_'+profile,[12,162,192],170+inv);hits=[(t,x) for t,x in events(s,'damage.accepted') if x['target']==s.session.world.resolve('boss')];assert next(x['amount'] for t,x in hits if t==170)==0;assert abs(next(x['amount'] for t,x in hits if t==162+inv)-286.8)<1e-8;areas=events(s,'area.resolved');assert areas and all(t>=191 for t,_ in areas);assert s.ctx.resources.current('player','hp')<34219;facts.append({'profile':profile,'HP_restored_at':161,'invul_expires':161+inv,'area_first':areas[0][0],'actual_true_invul170_zero':True,'actual_physical_afterinvul':286.8})
 FACTS['restored_profiles']=facts

def immunity():
 p=scene();p['buffs'] += [{'id':'buff/peer/v2/control'+str(flag),'kind':'buff','duration_seconds':1,'selection_flags':{'abnormal_flags':[flag]},'control':{'move':False,'attack':False,'abilities':False,'interrupt':True},'control_rule':'rule/ch9/mandra/stun_immunity','parameters':{'flags':[flag],'combos':[]}} for flag in [0,12,16]];p['scenarioDraft']['scheduledEffects']=[{'at':7+i,'effect':{'op':'apply_buff','target':2,'buff':'buff/peer/v2/control'+str(flag)}} for i,flag in enumerate([0,12,16])];s=proof(p,'immune_controls',[10],15);projection=s.ctx.spatial.selection_state('boss',DEFAULT_STATE);assert not set([0,12,16])&set(projection['abnormal_flags']);controls=s.ctx.buffs.controls('boss');assert controls['move'] and controls['attack'] and controls['abilities'];assert s.ctx.active('boss');assert all(b['applicability']['control'] is False for b in buffs(s) if b['definition'].startswith('buff/peer/v2/control'));FACTS['immune']={'flags_immunity_projected':projection['abnormal_immunes'],'actual_controls':controls,'foreigncaller_declaredcontrolrule_actual':True}

def leak():
 p=scene();p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1];p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':'WALK','startPosition':{'row':4,'col':4},'endPosition':{'row':4,'col':5},'checkpoints':[]};p['scenarioDraft']['objectives']={'type':'waves','life_resource':'life'};p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[]};s=proof(p,'native_leak2',[37],150);assert s.ctx.resources.current('system/battle','life')==99997;assert s.ctx.state().get('leaks',0)==1 and s.ctx.state().get('kills',0)==0;assert not s.ctx.alive('boss');FACTS['leak']={'life':99997,'leaks':1,'kills':0}

for name,fn in [('native_damage_mask',mask),('completed_rebirth_both_sourceprofiles',restored_profiles),('actual_source_control_immunity',immunity),('native_routeexit_loss2',leak)]:
 try:fn();RESULTS.append({'case':name,'passed':True})
 except Exception as e:RESULTS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
current=guard();r={'core':CORE,'actual_exit':0 if all(x['passed'] for x in RESULTS) and current==START else 1,'results':RESULTS,'facts':FACTS,'source_before':START,'source_after':current,'source_guard_equal':START==current,'artifacts':ART,'comparison_exclusions':[],'whole_stage':False};(OUT/'actual.fixturefixed.v2.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps({'actual_exit':r['actual_exit'],'results':RESULTS}));raise SystemExit(r['actual_exit'])
