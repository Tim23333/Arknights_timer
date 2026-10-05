"""Independent source Mandra modes/protocol tests, frozen modules/providers only."""
import sys,os,json,hashlib,traceback,math
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_mandra_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter09_mandra_v1.build import providers,BODY,SHIELD,RECOVERY,RAY,SLOW,SUMMON,TILE
CORE='06b9114b16965a43ab349ab019ee8ba2ae68c394c1955b9c1409639fc09cf323';assert implementation_digest()==CORE
FREEZE=ROOT/'validation/campaign/chapter09_mandra_v1/freeze.final.v1.json';BASE=ROOT/'packages/campaign/chapter09_consumers/mandra';OUT=ROOT/'validation/campaign/chapter09_mandra_peer';LOG=Path(os.environ['ARKSIM_RUN_DIR']);REG=providers();HP=41737;PEND='buff/ch9/mandra/pending_skin';TRAIT='buff/ch9/pillar/trait';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE;assert sha(FREEZE)=='e23d832c18eb5138a35271e931e35fe69bff2454d1b97902a0031445897fadba';f=json.loads(FREEZE.read_bytes());assert f['core_before']==f['core_after']==CORE
 for x in f['modules']:assert sha(ROOT/x['path'])==x['sha256']
 return {str(p):sha(p) for p in [FREEZE,BASE/'module.v1.json',BASE/'module.skill_prefix.v1.json',BASE/'consumer.requirements.v1.json',BASE/'source.token047.v1.json',ROOT/'tools/chapter09_mandra_v1/build.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts]}
START=guard();OUT.mkdir(parents=True,exist_ok=True);RESULTS=[];FACTS={};ART=[]
def actor(name,hp=34219,atk=1700,res=31):return {'id':'unit/peer/m/'+name,'kind':'entity','tags':['player',name],'components':{'attributes':{'base':{'max_hp':hp,'atk':atk,'def':727,'mres':res,'attack_speed_ratio':1.2,'block_count':1}},'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}}
def scene(profile='talent_prefix',near=False,lethal_player=False):
 p=json.loads((BASE/('module.v1.json' if profile=='talent_prefix' else 'module.skill_prefix.v1.json')).read_bytes());p['manifest']['requires']=['preset/ark_standard'];boss=next(e for e in p['entities'] if e['id']==BODY);boss['components']['attributes']['base'].update(max_hp=HP,atk=817,**{'def':683,'mres':39});boss['components']['resources']['hp'].update(initial=HP,capacity=HP)
 pillar=actor('pillar');pillar['components']['buffs']={'initial':[TRAIT]};ordinary=actor('ordinary',atk=140000);player=actor('player',hp=311 if lethal_player else 34219,atk=913);player2=actor('player2',atk=713);p['entities'] += [pillar,ordinary,player,player2];p['selectors'].append({'id':'selector/peer/m/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}],'limit':1});p['buffs'].append({'id':'buff/peer/m/stun','kind':'buff','duration_seconds':.5,'selection_flags':{'abnormal_flags':[0]},'control':{'abilities':False,'attack':False,'move':False,'interrupt':True}})
 for who,name,op in [('pillar','pillar_hit',{'op':'damage','damage_type':'true','scale':1}),('ordinary','lethal',{'op':'damage','damage_type':'true','scale':1}),('ordinary','stun',{'op':'apply_buff','buff':'buff/peer/m/stun'})]:
  aid='ability/peer/m/'+name;next(e for e in p['entities'] if e['id']=='unit/peer/m/'+who)['components']['abilities'].append(aid);p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/m/boss','timeline':[{'at':0,'effect':op}]})
 p['scenarioDraft']={'id':'scene/peer/m/'+profile+str(near),'ruleset':'ruleset/ark_standard','map':{'rows':11,'cols':12},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':BODY,'instanceAlias':'boss','position':{'row':4,'col':4}},{'definition':'unit/peer/m/pillar','instanceAlias':'pillar','position':{'row':9,'col':7}},{'definition':'unit/peer/m/ordinary','instanceAlias':'ordinary','position':{'row':9,'col':8}},{'definition':'unit/peer/m/player','instanceAlias':'player','position':{'row':4,'col':5} if near else {'row':9,'col':9}},{'definition':'unit/peer/m/player2','instanceAlias':'player2','position':{'row':4.7,'col':4.4} if near and not lethal_player else {'row':9,'col':10}}],'commands':[]};return p

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=41737683)
def events(s,t):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==t]
def buffs(s,who='boss'):return s.ctx.get(who,('buffs','instances'))
def state(s):return s.ctx.get('boss',('behavior','state'))
def proof(p,name,splits,end):
 a=create(p);a.advance(end);b=create(p);pins=[]
 for t in splits:
  b.advance(t-b.session.time);path=LOG/(name+str(t)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append({'path':str(path),'sha256':pin,'bytes':path.stat().st_size});b=Engine.restore(b.program,load_bound(path,pin),providers=REG)
 b.advance(end-b.session.time);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();ART.extend(pins);(OUT/(name+'.json')).write_text(json.dumps({'core':CORE,'actual_full_CPP_head_equal':True,'CPs':pins,'input_digest':digest(p)},indent=2),encoding='utf8');return a

def capture():
 p=scene();p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'pillar','ability':'ability/peer/m/pillar_hit'}];s=create(p);s.advance(8);assert s.ctx.resources.current('boss','hp')==HP-680;assert state(s)=='ground_open';b=next(x for x in buffs(s) if x['definition']==RECOVERY);assert abs(b['blackboard']['hp_ratio']-((HP-680)/HP-.4))<1e-10;assert not any(x['definition']==SHIELD for x in buffs(s));s=proof(p,'capture_original',[8],25);FACTS['capture']={'HP':HP,'raw_true1700':1700,'actual_shielded_damage':680,'captured_ratio':(HP-680)/HP-.4}

def controlled_skin():
 p=scene();p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'pillar','ability':'ability/peer/m/pillar_hit'},{'at':752,'action':'skill','source':'ordinary','ability':'ability/peer/m/stun'}];s=proof(p,'recovery25_pending',[758,770],820);starts=[t for t,x in events(s,'ability.started') if x['ability']=='ability/ch9/mandra/restore_skin'];assert len(starts)==1 and starts[0]>=767;ends=[t for t,x in events(s,'ability.finished') if x['ability']=='ability/ch9/mandra/restore_skin'];assert ends==[starts[0]+45];assert s.ctx.resources.current('boss','hp')==HP-680;assert state(s)=='ground_stone';assert not any(x['definition'] in [RECOVERY,PEND] for x in buffs(s));FACTS['controlled_skin']={'start':starts[0],'finish':ends[0],'source_recovery_expiry':757,'HPunchanged_after_capture':True}

def profiles():
 for profile,inv,cd in [('talent_prefix',90,600),('skill_prefix',150,300)]:
  p=scene(profile);p['scenarioDraft']['commands']=[{'at':11,'action':'skill','source':'ordinary','ability':'ability/peer/m/lethal'}];s=create(p);s.advance(12);assert s.ctx.resources.current('boss','hp')==0 and state(s)=='fly_stone';assert not s.ctx.active('boss');assert s.ctx.get('boss',('runtime','cooldowns',RAY))==311;assert s.ctx.get('boss',('runtime','cooldowns',SUMMON))==11+cd;b=next(x for x in buffs(s) if x['definition']=='buff/ch9/mandra/invulnerable');assert b['expires_at']==11+inv;s.advance(150);assert s.ctx.resources.current('boss','hp')==HP;s=proof(p,'profile_'+profile,[12,162],200);assert state(s)=='fly_stone';assert s.ctx.get('boss',('selection_state','motion'))==2 and s.ctx.get('boss',('spatial','route_motion_mode'))==0
 FACTS['two_profiles']={'first_zero':11,'HP_restore':161,'talent_invul90_skill150':True,'talent_summon600_skill300':True}

def ray_modifier():
 p=scene(near=True);p['buffs'] += [{'id':'buff/peer/m/atk','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':1000}]},{'id':'buff/peer/m/res','kind':'buff','modifiers':[{'attribute':'mres','layer':'flat','value':10}]}];p['scenarioDraft']['scheduledEffects']=[{'at':140,'effect':{'op':'apply_buff','target':6,'buff':'buff/peer/m/atk'}},{'at':160,'effect':{'op':'apply_buff','target':6,'buff':'buff/peer/m/res'}}];s=proof(p,'ray_modified_highest',[159,163],193);packets=events(s,'damage.accepted');assert packets and all(x['target']==s.session.world.resolve('player2') for _,x in packets);assert abs(s.ctx.attributes.value('player2','attack_speed_ratio')-.36)<1e-10;assert all(abs(x['amount']-482.03)<1e-8 for _,x in packets);assert s.ctx.resources.current('player','hp')==34219;FACTS['ray']={'packet_times':[t for t,_ in packets],'target_actual_ATK1713':True,'perpacket_atk817_RES41_loss482_03':True}

def targetdeath047():
 p=scene(near=True,lethal_player=True);s=proof(p,'ray_targetdeath047',[159],190);assert not s.ctx.alive('player');tokens=[e for e in s.session.world.entities() if e['definition_id']=='unit/ch9/mandra/sealed_ground'];assert len(tokens)==1;token=tokens[0];assert 'resources' not in token['components'];assert s.ctx.get(token['id'],('ownership','owner'))==s.session.world.resolve('boss');FACTS['token047']={'no_fabricated_HP':True,'actual_owned_deadtarget_cell_spawn':True,'position':thaw(token['components']['spatial']['position'])}

def summon_auto5():
 p=scene();p['scenarioDraft']['commands']=[{'at':11,'action':'skill','source':'ordinary','ability':'ability/peer/m/lethal'}];s=proof(p,'summon_real5',[632,783],830);born=[e for e in s.session.world.entities() if e['definition_id']=='unit/ch9/mandra/auto_pillar'];assert len(born)==1;assert not s.ctx.alive(born[0]['id']);assert len(events(s,'tile.token_created'))==3;FACTS['summon']={'actual_pillar5s_collapse':True,'token_count3_including_pillar_and2ruins':True}

def capture_tamper():
 p=scene();p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'pillar','ability':'ability/peer/m/pillar_hit'}];s=create(p);s.advance(8);cp=s.checkpoint();owner_id=cp['kernel']['world']['aliases']['boss'];bad=deepcopy(cp);actor=next(e for e in bad['kernel']['world']['entities'] if e['id']==owner_id);b=next(x for x in actor['components']['buffs']['instances'] if x['definition']==RECOVERY);b['blackboard']['hp_ratio']+=.01
 try:Engine.restore(s.program,bad,providers=REG)
 except ValueError as e:FACTS['capture_tamper']={'rejected':True,'actual_reason':str(e),'natural_cache_unchanged':bad['attribute_cache']==cp['attribute_cache']}
 else:raise AssertionError('capture memory tamper accepted')


def skip_and_latefault():
 p=scene();s=create(p);s.ctx.effects.execute('ordinary',['boss'],{'op':'apply_buff','buff':'buff/peer/m/stun'});before=s.checkpoint();effect={'op':'trigger_ability','target':'selected','ability':'ability/ch9/mandra/restore_skin'}
 try:s.ctx.effects.execute('boss',['boss'],effect)
 except ValueError as e:assert 'control' in str(e).lower()
 else:raise AssertionError('default trigger unexpectedly skipped')
 assert s.checkpoint()==before;s.ctx.effects.execute('boss',['boss'],{**effect,'parameters':{'on_rejection':'skip'}});assert not [x for _,x in events(s,'ability.started') if x['ability']=='ability/ch9/mandra/restore_skin']
 p=scene();next(b for b in p['buffs'] if b['id']==RECOVERY)['on_remove'].append({'op':'apply_buff','target':'source','buff':'buff/peer/m/fault'});p['buffs'].append({'id':'buff/peer/m/fault','kind':'buff','effects':[{'op':'random','stream':'peer.mandra_fault','probability':1,'on_success':[{'op':'emit','event':'peer.before_mandra_fault'}]},{'op':'modify_resource','resource':'missing','amount':1}]});s=create(p);s.ctx.effects.execute('pillar',['boss'],{'op':'damage','damage_type':'true','scale':1});s.ctx.attributes.value('boss','def');before=s.checkpoint()
 try:s.ctx.effects.execute('boss',['boss'],{'op':'remove_buff','buff':RECOVERY})
 except ValueError as e:assert 'missing' in str(e)
 else:raise AssertionError('late holder fault accepted')
 assert s.checkpoint()==before;assert s.session.random.samples==();FACTS['fault']={'skip_only_actual_activationrejected':True,'default_rejection_raised':True,'late_random_missing_resource_full_rollback':True}

for name,fn in [('capture_current_HP_minus_point4',capture),('25sec_controlled_pending_Skin45frames',controlled_skin),('native_two_life_prefix_profiles',profiles),('Ray_current_highest_modified_ATK_RES_slow',ray_modifier),('actual_deadtarget_owned_047',targetdeath047),('actual_real_pillar_auto5',summon_auto5),('capture_checkpoint_tamper',capture_tamper),('skipdefault_and_lateholderfault',skip_and_latefault)]:
 try:fn();RESULTS.append({'case':name,'passed':True})
 except Exception as e:RESULTS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
current=guard();report={'core':CORE,'actual_exit':0 if all(x['passed'] for x in RESULTS) and current==START else 1,'results':RESULTS,'facts':FACTS,'source_before':START,'source_after':current,'source_guard_equal':current==START,'artifacts':ART,'comparison_exclusions':[],'whole_stage':False};(OUT/'actual.initial.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({'actual_exit':report['actual_exit'],'results':RESULTS}));raise SystemExit(report['actual_exit'])
