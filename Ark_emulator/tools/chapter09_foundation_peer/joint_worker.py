"""Independent content-authored element/sight/SP clock and cache forgery gate."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw,digest
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE

def fixture(retire=False):
 def rule(name,contract,expr):return {'id':'rule/joint/'+name,'kind':'rule','contract':contract,'implementation':{'type':'expression','expression':expr}}
 rules=[rule('capacity','elemental.capacity','inputs.parameters.capacity'),rule('loss','elemental.loss','inputs.request.raw_amount'),rule('recovery','elemental.recovery','min(inputs.capacity, inputs.current + inputs.parameters.recovery_rate * inputs.delta_seconds)'),rule('duration','elemental.break_duration','inputs.parameters.break_duration_seconds'),rule('element-eligible','elemental.eligibility','True'),rule('sp','resource.recovery','inputs.current + inputs.attributes.sp_regen * inputs.delta_seconds'),{'id':'rule/joint/eligible','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}}]
 callbacks=[{'op':'apply_buff','target':'source','buff':'buff/joint/sight'}]
 if retire:callbacks += [{'op':'retire','target':'source','parameters':{'reason':'joint_retired'}},{'op':'modify_resource','target':'source','resource':'sp','delta':31}]
 element={'eligibility_rule':'rule/joint/element-eligible','elements':{'peer_FOG':{'capacity':37,'resistance':0,'recovery_rate':1.7,'break_duration_seconds':.7,'rules':{'elemental.'+name:'rule/joint/'+key for name,key in [('capacity','capacity'),('loss','loss'),('recovery','recovery'),('break_duration','duration')]},'on_break':callbacks,'on_end':[{'op':'remove_buff','target':'source','buff':'buff/joint/sight'}]}}}
 config={k:False for k in ('_ignoreTargetFree','_onlyIgnoreSomeOfTargetFreeCase','_excludeSomeAbnormalFlags','_needProfessionMask','_ignoreAllyTargetFree','_ignoreHealFree','_ignoreMotionMode','_forceIgnoreCamouflage','_checkUnitType')};config.update(_targetSide=2,_targetCategory=1,_targetMotion=1)
 selector={'id':'selector/joint','kind':'selector','region':{'type':'radius','radius':4.2},'eligibility':{'rule':'rule/joint/eligible','parameters':{'source_configuration':config,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':copy.deepcopy(DEFAULT_STATE)}}}
 actor={'id':'unit/joint/seer','kind':'entity','components':{'attributes':{'base':{'max_hp':587,'atk':41,'def':9,'sp_regen':2}},'resources':{'hp':{'initial':587,'capacity':587,'role':'health'},'sp':{'initial':0,'capacity':173,'recovery_rule':'rule/joint/sp'}},'spatial':{},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'abilities':['ability/joint/break','ability/joint/probe'],'elemental':element}}
 shade={'id':'unit/joint/shade','kind':'entity','components':{'attributes':{'base':{'max_hp':611,'atk':13,'def':3}},'resources':{'hp':{'initial':611,'capacity':611,'role':'health'}},'spatial':{},'selection_state':{'side':1,'category':1,'motion':1,'unit_type':1,'abnormal_flags':[9]}}}
 abilities=[{'id':'ability/joint/break','kind':'ability','activation':{'mode':'manual'},'duration_seconds':.2,'timeline':[{'at_seconds':0,'effect':{'op':'elemental_damage','target':2,'element':'peer_FOG','amount':37}}]},{'id':'ability/joint/probe','kind':'ability','activation':{'mode':'manual'},'selector':'selector/joint','target_capture':'at_cast','duration_seconds':.2,'timeline':[{'at_seconds':.1,'effect':{'op':'damage','damage_type':'physical','scale':1}}]}]
 return {'schemaVersion':2,'manifest':{'id':'package/joint/peer','requires':['preset/ark_standard']},'entities':[actor,shade],'rules':rules,'selectors':[selector],'abilities':abilities,'buffs':[{'id':'buff/joint/sight','kind':'buff','selection_flags':{'can_select_invisible':True},'modifiers':[{'attribute':'sp_regen','layer':'flat','value':11}]}],'scenarioDraft':{'id':'scene/joint/peer','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':5},'initialEntities':[{'definition':actor['id'],'instanceAlias':'seer','position':{'row':0,'col':0}},{'definition':shade['id'],'instanceAlias':'shade','position':{'row':1,'col':3}}]}}

def main():
 checks=[]
 def check(name,value):assert value,name;checks.append(name)
 data=fixture();p=Compiler().compile(data);s=Engine.create(p,seed=85031);qual=lambda sim:sim.ctx.spatial.qualifies('seer','shade',p.definitions['selector/joint'])
 check('initial9 denies source',not qual(s));s.submit({'action':'skill','source':'seer','ability':'ability/joint/break'},at=13);s.submit({'action':'skill','source':'seer','ability':'ability/joint/probe'},at=22);s.advance(15)
 state=s.ctx.get('seer',('runtime','elemental'));check('on_break13 owns21tick duration due34',state['break']['due']==34);check('on_break sight source grant',qual(s));check('on_break SP recovery modifier13',s.ctx.attributes.value('seer','sp_regen')==13);check('on_break recovery faster than base',s.ctx.resources.current('seer','sp')>2*15/30)
 s.ctx.attributes.values('seer');cp=s.checkpoint();path=Path(sys.argv[2]).parent/'joint.pending.checkpoint.json';path.write_text(json.dumps(cp),encoding='utf8');r=Engine.restore(p,json.loads(path.read_bytes()));check('pending actualCPP identity',s.checkpoint()==r.checkpoint())
 s.ctx.attributes.values('seer');r.ctx.attributes.values('seer');check('pendingCP legal query causal events',thaw(list(s.session.events))==thaw(list(r.session.events)))
 for time in (23,33,34,35):
  s.advance(time-s.session.time);r.advance(time-r.session.time);check('CPP full events time'+str(time),thaw(list(s.session.events))==thaw(list(r.session.events)));check('CPP full checkpoint time'+str(time),s.checkpoint()==r.checkpoint())
  if time==33:check('sight retained before halfopen end34',qual(s));check('break locked before34',s.ctx.get('seer',('runtime','elemental'))['break'] is not None)
  if time==34:check('advance interval excludes34 scheduled callback',qual(s) and s.ctx.get('seer',('runtime','elemental'))['break']['due']==34)
  if time==35:
   check('on_end executes at34 then removes sight',not qual(s));check('on_end SP modifier expires to2',s.ctx.attributes.value('seer','sp_regen')==r.ctx.attributes.value('seer','sp_regen')==2);check('end34 resets capacity37',s.ctx.get('seer',('runtime','elemental'))['remaining']['peer_FOG']==37);check('break ended eventtime34',any(e['type']=='elemental.break.ended' and e['time']==34 for e in s.session.events));check('postend legal query CPP all events',thaw(list(s.session.events))==thaw(list(r.session.events)))
 check('sighted probe damages invisible target',s.ctx.resources.current('shade','hp')<611)
 # Replay a pure public-command history separately: direct observation calls
 # are not encoded by command replay and are therefore not silently discarded.
 head_source=Engine.create(p,seed=85031);head_source.submit({'action':'skill','source':'seer','ability':'ability/joint/break'},at=13);head_source.submit({'action':'skill','source':'seer','ability':'ability/joint/probe'},at=22);head_source.advance(35);head=replay(p,head_source.export_replay());check('publiccommands head all events',thaw(list(head_source.session.events))==thaw(list(head.session.events)));check('publiccommands head full checkpoint',head_source.checkpoint()==head.checkpoint())
 # Strong forgery negatives recompute record digests where appropriate.
 negatives=[]
 def resign(row):row['record_digest']=digest({k:v for k,v in row.items() if k!='record_digest'})
 def reject(name,mutate):
  changed=copy.deepcopy(cp);mutate(changed)
  try:Engine.restore(p,changed)
  except (ValueError,KeyError):negatives.append(name)
  else:raise AssertionError('forged CP accepted '+name)
 rows=cp['attribute_cache']['entries'];check('real liveCP attribute cache populated',bool(rows))
 reject('runtimeFP',lambda c:c.__setitem__('runtime_fingerprint','a'*64))
 reject('cache rulesFP',lambda c:c['attribute_cache'].__setitem__('rules_fingerprint','a'*64))
 def forged_value(c):row=c['attribute_cache']['entries'][0];row['value']+=.125;resign(row)
 reject('value with recomputed cache digest',forged_value)
 def forged_owner(c):row=c['attribute_cache']['entries'][0];row['owner']=3;resign(row)
 reject('owner with recomputed cache digest',forged_owner)
 def forged_context(c):
  row=c['attribute_cache']['entries'][0];event=c['kernel']['events']['records'][row['source_event_id']-1];event['payload']['trace']['context']['attribute_sample_time']=-67;row['event_digest']=digest(event);resign(row)
 reject('actual context with recomputed event and cache digest',forged_context)
 def unknownfp(c):row=c['attribute_cache']['entries'][0];row['unknown_fingerprint']='a'*64;resign(row)
 reject('unknownFP with recomputed cache digest',unknownfp)
 def wrongscope(c):row=c['attribute_cache']['entries'][0];row['ability']={'parameters':{'peer_scope':1}};resign(row)
 reject('requestscope with recomputed cache digest',wrongscope)
 # Break callback retirement cancels lifecycle lease and later callback writes.
 rp=Compiler().compile(fixture(retire=True));rs=Engine.create(rp,seed=85031);rs.submit({'action':'skill','source':'seer','ability':'ability/joint/break'},at=13);rs.advance(15);check('on_break owner retirement cancels owned lease',not rs.ctx.active('seer') and rs.ctx.get('seer',('runtime','elemental'))['break'] is None);check('postretire callback31 cannot changeSP',rs.ctx.resources.current('seer','sp')<31);check('retired sightowner cannot select',not rs.ctx.spatial.qualifies('seer','shade',rp.definitions['selector/joint']));count=len([e for e in rs.session.events if e['type']=='elemental.break.ended']);rs.advance(35);check('cancelled owner no stale endcallback',len([e for e in rs.session.events if e['type']=='elemental.break.ended'])==count)
 out={'implementation':implementation_digest(),'checks':checks,'negative_checks':negatives,'fresh_fixture':{'capacity':37,'break_at':13,'due':34,'duration_seconds':.7,'sp_rates':[2,13],'seed':85031,'element':'peer_FOG'},'passed':True};Path(sys.argv[2]).write_text(json.dumps(out,indent=2),encoding='utf8')
if __name__=='__main__':main()
