"""Fresh peer fixture; no imports from invisible author/root fixtures."""
import sys,json,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,sys.argv[1]);sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.selection import DEFAULT_STATE,validate_state
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference

def base():
 state={k:copy.deepcopy(v) for k,v in DEFAULT_STATE.items()}
 config={k:False for k in ('_ignoreTargetFree','_onlyIgnoreSomeOfTargetFreeCase','_excludeSomeAbnormalFlags','_needProfessionMask','_ignoreAllyTargetFree','_ignoreHealFree','_ignoreMotionMode','_forceIgnoreCamouflage','_checkUnitType')}
 config.update(_targetSide=2,_targetCategory=1,_targetMotion=1)
 selector={'id':'selector/peer','kind':'selector','region':{'type':'radius','radius':4.3},'filters':[{'state':'alive'}],'eligibility':{'rule':'rule/peer/eligible','parameters':{'source_configuration':config,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':state}}}
 def unit(name,side,flags):return {'id':'unit/'+name,'kind':'entity','components':{'attributes':{'base':{'max_hp':473,'atk':29,'def':7}},'resources':{'hp':{'initial':473,'capacity':473,'role':'health'}},'spatial':{},'selection_state':{'side':side,'motion':1,'category':1,'unit_type':1,'abnormal_flags':flags},'abilities':['ability/peer'] if name=='seer' else []}}
 buffs=[{'id':'buff/'+name,'kind':'buff','selection_flags':flags,**extra} for name,flags,extra in [('hidden',{'abnormal_flags':[9]},{'active_rule':'rule/peer/awake','duration_seconds':1.3}),('sight',{'can_select_invisible':True},{'active_rule':'rule/peer/awake'}),('silence',{'abnormal_flags':[12]},{}),('immune',{'abnormal_immunes':[9]},{}),('camo',{'abnormal_flags':[17]},{}),('free',{'abnormal_flags':[2]}, {})]]
 rules=[{'id':'rule/peer/eligible','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}},{'id':'rule/peer/awake','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'12 not in inputs.status.abnormal_flags'}}]
 ability={'id':'ability/peer','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer','target_capture':'at_cast','duration_seconds':.6,'timeline':[{'at_seconds':.4,'effect':{'op':'damage','damage_type':'physical','scale':1}}]}
 return {'schemaVersion':2,'manifest':{'id':'package/peer','requires':['preset/ark_standard']},'entities':[unit('seer',0,[]),unit('shade',1,[]),unit('other',1,[])],'buffs':buffs,'rules':rules,'selectors':[selector],'abilities':[ability],'scenarioDraft':{'id':'scene/peer','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':6},'initialEntities':[{'definition':'unit/seer','instanceAlias':'seer','position':{'row':0,'col':0}},{'definition':'unit/shade','instanceAlias':'shade','position':{'row':0,'col':3}},{'definition':'unit/other','instanceAlias':'other','position':{'row':1,'col':2}}],'scheduledEffects':[{'at':0,'effect':{'op':'apply_buff','target':{'alias':'shade'},'buff':'buff/hidden'}}]}}

def independent():
 data=base();data['scenarioDraft'].pop('scheduledEffects');data['entities'][0]['components']['abilities'].append('ability/reserve');data['abilities'].append({'id':'ability/reserve','kind':'ability','activation':{'mode':'manual'},'duration_seconds':1,'timeline':[{'at_seconds':0,'effect':{'op':'apply_buff','target':'source','buff':b['id']}} for b in data['buffs']]});p=Compiler().compile(data);s=Engine.create(p,seed=72613);ctx=s.ctx;sel=p.definitions['selector/peer'];q=lambda:ctx.spatial.qualifies('seer','shade',sel)
 checks=[]
 def check(name,value):assert value,name;checks.append(name)
 check('ordinary visible',q());hid=ctx.buffs.apply('shade','shade','buff/hidden');check('9 invisible only',not q() and ctx.spatial.selection_state('shade',DEFAULT_STATE).get('invisible') is True and not ctx.spatial.selection_state('shade',DEFAULT_STATE)['camouflage'] and not ctx.spatial.selection_state('shade',DEFAULT_STATE)['target_free'])
 for switch in ('_forceIgnoreCamouflage','_ignoreTargetFree'):
  probe=thaw(sel);probe['eligibility']['parameters']['source_configuration'][switch]=True;check(switch+' cannot authorize invisible',not ctx.spatial.qualifies('seer','shade',probe))
 sight=ctx.buffs.apply('other','seer','buff/sight');check('source Buff grants sight',q());ctx.buffs.apply('seer','seer','buff/silence');check('source silence suspends sight',not q());ctx.buffs.remove('seer','buff/silence');check('sight resumes',q());ctx.buffs.remove('seer',sight);check('owner removal drops sight',not q())
 ctx.buffs.apply('seer','shade','buff/silence');check('target silence suspends hidden',q());ctx.buffs.remove('shade','buff/silence');check('hidden resumes',not q());ctx.buffs.apply('seer','shade','buff/immune');check('9 immune removes derived invis',q());ctx.buffs.remove('shade','buff/immune');check('immune remove restores hidden',not q());ctx.buffs.remove('shade',hid);check('hidden owner removal',q())
 for buff,key in [('camo','camouflage'),('free','target_free')]:
  uid=ctx.buffs.apply('seer','shade','buff/'+buff);state=ctx.spatial.selection_state('shade',DEFAULT_STATE);check(key+' separate from invisible',state[key] and not state.get('invisible',False));ctx.buffs.remove('shade',uid)
 ctx.buffs.apply('seer','shade','buff/hidden');s.advance(39);check('half open expiry at39',q())
 # Contributions are owned by the target; source retirement grants no
 # permission to other actors and cannot let a retired actor select.
 ctx.buffs.apply('shade','shade','buff/hidden');ctx.buffs.apply('other','seer','buff/sight');check('sight belongs to target owner',q() and not ctx.spatial.selection_state('other',DEFAULT_STATE).get('can_select_invisible',False));ctx.lifecycle.retire('other','peer_retired');check('ordinary foreign source retire retains owned sight',q());ctx.buffs.remove('seer','buff/sight');check('owned remove after grant source retire',not q());ctx.buffs.apply('shade','seer','buff/sight');ctx.lifecycle.retire('seer','peer_retired');check('retired sight owner cannot qualify',not q())
 for key in ('invisible','can_select_invisible'):
  for value in (1,0,'true',None,[],{}):
   try:validate_state({key:value})
   except ValueError:checks.append('strict '+key+' '+repr(value))
   else:raise AssertionError('accepted bad bool')
 try:validate_state({'alien_invisible':True})
 except ValueError:checks.append('unknown field rejected')
 else:raise AssertionError('unknown field')
 # Genuine public commands plus actual checkpoint roundtrip, fresh world.
 s=Engine.create(p,seed=72613);s.submit({'action':'skill','source':'seer','ability':'ability/peer'},at=7);s.advance(11)
 cp=s.checkpoint();cp_path=Path(sys.argv[2]).parent/'actual.checkpoint.json';cp_path.write_text(json.dumps(cp));restored=Engine.restore(p,json.loads(cp_path.read_bytes()));s.advance(22);restored.advance(22);check('actual CP all event values',thaw(list(s.session.events))==thaw(list(restored.session.events)));check('actual CP full state',s.checkpoint()==restored.checkpoint());head=replay(p,s.export_replay());check('public command head all events',thaw(list(s.session.events))==thaw(list(head.session.events)));check('public command head full state',s.checkpoint()==head.checkpoint())
 # A captured projectile keeps its declared retain/hit-on-reach policy.
 data['rules'] += [{'id':'rule/peer/'+name,'kind':'rule','contract':'projectile.'+contract,'implementation':{'type':'provider','provider':'model.projectile.'+contract}} for name,contract in [('motion','trajectory'),('collision','collision')]]
 data['projectiles']=[{'id':'projectile/peer','kind':'projectile','motion':{'rule':'rule/peer/motion','parameters':{'mode':'homing','speed':4.7}},'collision':{'rule':'rule/peer/collision','parameters':{'enabled':False}},'lifetime_seconds':2.7,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,'completion_blocking':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True}}]
 effect=data['abilities'][0]['timeline'][0]['effect'];effect['projectile_definition']='projectile/peer';p2=Compiler().compile(data);s2=Engine.create(p2,seed=72613);s2.advance(5);projectile=s2.ctx.projectiles.launch('seer','shade',effect,p2.definitions['ability/peer'],{},None);s2.ctx.buffs.apply('seer','shade','buff/hidden');check('captured projectile invisible acquisition denies later selection',not s2.ctx.spatial.qualifies('seer','shade',p2.definitions['selector/peer']));s2.ctx.lifecycle.retire('seer','peer_retired');s2.advance(23);check('captured projectile retains authorized hit after invisible and source retirement',s2.ctx.resources.current('shade','hp')<473)
 # Use the actual ordinary source selector, with independently supplied state.
 from tools.chapter08_bsnake_combat.policies_v1 import providers
 ordinary=json.loads((ROOT/'packages/campaign/chapter09_consumers/ordinary/enemy_1167_dubow.module.v1.json').read_bytes());ordinary['entities'].append({'id':'unit/peer/ordinary','kind':'entity','components':{'attributes':{'base':{'max_hp':541}},'resources':{'hp':{'initial':541,'capacity':541,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1,'abnormal_flags':[9]}}});ordinary['scenarioDraft']={'id':'scene/peer/ordinary','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':ordinary['entities'][0]['id'],'instanceAlias':'enemy','position':{'row':0,'col':0}},{'definition':'unit/peer/ordinary','instanceAlias':'guard','position':{'row':0,'col':1}}]};reg=providers();op=Compiler(providers=reg).compile(ordinary);osim=Engine.create(op,providers=reg,seed=72613);selector=next(v for v in op.definitions.values() if v.get('kind')=='selector');check('actual ordinary source typed selector denies9',not osim.ctx.spatial.qualifies('enemy','guard',selector));state=osim.ctx.get('enemy',('selection_state',));state['can_select_invisible']=True;osim.ctx.set('enemy',('selection_state',),state);check('actual ordinary explicit source sight grants9',osim.ctx.spatial.qualifies('enemy','guard',selector))
 return {'implementation':implementation_digest(),'checks':checks,'passed':True}

def legacy():
 from tools.chapter08_bsnake_combat.policies_v1 import providers
 reg=providers();cases={}
 for enemy in ('enemy_1165_duhond','enemy_1166_dusbr','enemy_1167_dubow'):
  data=json.loads((ROOT/'packages/campaign/chapter09_consumers/ordinary'/(enemy+'.module.v1.json')).read_bytes());uid=data['entities'][0]['id'];ranged=enemy.endswith('dubow')
  data['entities'].append({'id':'unit/peer/guard','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':7731,'def':181,'mres':63,'block_count':1}},'resources':{'hp':{'initial':7731,'capacity':7731,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'deployable':{'base_cost':1,'terrain':'ground','capacity':1,'cooldown_seconds':0},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
  data['scenarioDraft']={'id':'scene/peer/'+enemy,'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},'resources':{'dp':{'initial':13,'capacity':97}},'roster':['unit/peer/guard'],'commands':[{'at':0,'action':'deploy','entity':'unit/peer/guard','alias':'guard','row':0,'col':1}],'initialEntities':[{'definition':uid,'instanceAlias':'enemy','position':{'row':0,'col':0 if ranged else 1},**({} if ranged else {'route':{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':4},'checkpoints':[]}})}]}
  p=Compiler(providers=reg).compile(data);s=Engine.create(p,seed=72613,providers=reg);captures=[]
  for t in (0,17,83):s.advance(t-s.session.time);captures.append({'checkpoint':s.checkpoint(),'events':thaw(list(s.session.events)),'state':thaw(s.ctx.state())})
  cases[enemy]={'program_fingerprint':p.fingerprint,'runtime_fingerprint':s.runtime_fingerprint,'definitions':thaw(p.definitions),'scenario':thaw(p.scenario),'metadata':thaw(p.metadata),'captures':captures}
 return {'implementation':implementation_digest(),'cases':cases}
def cache_scope():
 data=base();data['buffs']=[b for b in data['buffs'] if b['id']=='buff/hidden'];data['scenarioDraft'].pop('scheduledEffects');p=Compiler().compile(data);s=Engine.create(p,seed=72613);s.advance(11);s.ctx.attributes.values('seer');cp=s.checkpoint();r=Engine.restore(p,json.loads(json.dumps(cp)));before=len(s.session.events);v=s.ctx.attributes.values('seer');rv=r.ctx.attributes.values('seer');a,b=thaw(list(s.session.events)),thaw(list(r.session.events));return {'implementation':implementation_digest(),'legal_attribute_value_equal':v==rv,'all_events_equal':a==b,'first_difference':first_difference(a,b),'original_event_count':len(a),'restored_event_count':len(b),'idle_checkpoint_time':11,'original_query_appended_events':len(a)-before,'restored_query_appended_events':len(b)-before,'scope':'Preexisting derived attribute cache restore query semantics; no invisible fields in compiled program','passed':a==b}
mode=sys.argv[3]
Path(sys.argv[2]).write_text(json.dumps(independent() if mode=='independent' else cache_scope() if mode=='cache' else legacy(),ensure_ascii=False,separators=(',',':')),encoding='utf8')
