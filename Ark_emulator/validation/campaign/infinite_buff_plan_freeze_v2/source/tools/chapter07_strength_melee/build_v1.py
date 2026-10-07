"""Three exact ordinary melee variants, conditional literal BSON listeners."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.chapter07_strength_melee.policies_v1 import providers
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()=='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
 source=ROOT/'packages/campaign/chapter07_sources/native.reference.json';plan=ROOT/'packages/campaign/chapter07_consumption_plan/source.consumption.plan.json';parent=ROOT/'packages/campaign/chapter07_ordinary/sotihd.module.v4.reference.json';d=json.loads(source.read_bytes());plans=json.loads(plan.read_bytes());outputs=[]
 for vid,v in d['variants'].items():
  if not any(n in vid for n in ('sotisc@','sotiab@','sotiab_2@')):continue
  row=next(r for r in plans['exact12_variants'] if r['variant_id']==vid);native=v['native_enemy']['resolved'];a=native['attributes'];stat='move_speed' if 'sotisc@' in vid else 'atk';bb=next(b['value'] for b in native['talentBlackboard'] if b['key']=='strength.'+stat);listeners=v['passive_and_skill_components'][0]['raw']['_buffs'];assert len(listeners)==2 and all(b['triggerInterval']==.25 and b['waitFirstTriggerInterval']==1 for b in listeners)
  for b in listeners:
   doc=row['literal_BSON_templates'][b['templateKey']]['parsed'];actions=doc['eventToActions']['ON_BUFF_TRIGGER'];assert actions[0]['_buffKeys']==['enemy_9D0_talent_strength'] and not actions[0]['_checkBuffSource']
  p=json.loads(parent.read_bytes());name=vid.split('@')[0];old=p['entities'][0]['id'];new='unit/ch7/strength/'+name;oldA=p['abilities'][0]['id'];oldS=p['selectors'][0]['id'];oldB=p['behaviors'][0]['id'];text=json.dumps(p).replace(old,new).replace(oldA,'ability/ch7/strength/'+name).replace(oldS,'selector/ch7/strength/'+name).replace(oldB,'behavior/ch7/strength/'+name);p=json.loads(text)
  unit=p['entities'][0];base=unit['components']['attributes']['base'];base.update(max_hp=a['maxHp'],atk=a['atk'],def_=a['def']);base.pop('def_');base['def']=a['def'];base.update(mres=a['magicResistance'],move_speed=a['moveSpeed'],attack_interval=a['baseAttackTime'],attack_speed_ratio=a['attackSpeed']/100,mass_level=a['massLevel']);unit['components']['resources']['hp'].update(initial=a['maxHp'],capacity=a['maxHp']);unit['metadata'].update(native_variant=vid,native_reference=v['native_reference'])
  frame=next(e for e in v['modes'][0]['nodes']['_combat']['animation_binding']['events'] if e['name']=='OnAttack');p['abilities'][0]['timeline'][0]['at_seconds']=frame['seconds'];p['abilities'][0]['metadata']={'source_combat':v['modes'][0]['nodes']['_combat'],'native_OnAttack_frame':frame['frame']}
  marker='buff/ch7/source/enemy_9D0_talent_strength';derived='buff/ch7/source/enemy_talent_strength['+stat+']';p['buffs']=[{'id':marker,'kind':'buff','metadata':{'source_role':'External source marker identity; emitter separate, no invented stat buff'}},{'id':derived,'kind':'buff','stacking':{'mode':'refresh','identity':['definition','target'],'max_stacks':1},'modifiers':[{'attribute':stat,'layer':'percent','value':bb}],'metadata':{'native_BSON_create':row['literal_BSON_templates'][listeners[0]['templateKey']]['parsed'],'sourceBB':native['talentBlackboard']}}]
  ids=[]
  for mode,b in zip(('start','finish'),listeners):
   rid='rule/ch7/strength/'+name+'/'+mode;bid='buff/ch7/strength/'+name+'/'+mode;ids.append(bid);p['rules'].append({'id':rid,'kind':'rule','contract':'buff.application','implementation':{'type':'provider','provider':'reference.ch7.strength_listener'},'parameters':{'marker':marker,'derived':derived,'mode':mode}});p['buffs'].append({'id':bid,'kind':'buff','interval_seconds':b['triggerInterval'],'effects':[{'op':'buff_application','application_rule':rid,'allowed':[derived]}],'metadata':{'native_listener':b,'literal_BSON':row['literal_BSON_templates'][b['templateKey']]}})
  unit['components']['buffs']={'initial':ids};p['manifest']['id']='package/ch7/strength/'+name+'/v1';p['manifest']['metadata']={'required_runtime':implementation_digest(),'source_locks':{str(f):sha(f) for f in (source,plan,parent,Path(__file__),ROOT/'tools/chapter07_strength_melee/policies_v1.py')},'variant_bindings':[{'variant_id':vid,'native_reference':v['native_reference'],'native_resolved':native}],'reference_policy':'.25seconds periodic first tick8 via existing quantum ceil. Literal owner CheckContainsBuff marker; no source filtering; source start only if derived absent, finish only if marker absent. Captured-live melee and ASPD timing reference inherited from explicitly pinned ordinary recipe, native method body/client pending.','client_verified':False}
  fixture=deepcopy(p);fixture['scenarioDraft']={'id':'scene/ch7/strength/compile/'+name,'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},'objectives':{},'initialEntities':[{'definition':new,'instanceAlias':'source','position':{'row':0,'col':0}}]};Compiler(providers=providers()).compile(fixture)
  dest=ROOT/'packages/campaign/chapter07_strength_melee'/('module.'+name+'.v1.json');dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();dest.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');outputs.append({'variant':vid,'module':str(dest),'sha':sha(dest),'actual_compile':True})
 print(json.dumps(outputs))
if __name__=='__main__':main()
