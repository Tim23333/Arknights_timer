"""Three exact ore-responsive demon variants, including effective animation hooks."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'packages/campaign/chapter07_boss/demons'
SOURCE=ROOT/'packages/campaign/chapter07_sources/native.reference.json'
PLAN=ROOT/'packages/campaign/chapter07_consumption_plan/source.consumption.plan.json'
IDS=['enemy_1084_sotidm@0/36d5cfd40d4f58cb','enemy_1085_sotiwz@0/e124b5c8af77c515','enemy_1085_sotiwz_2@0/eaaf6bc64dae9f1c']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert sha(SOURCE)=='8bd457cc8f24d154b304a8cf0a946b9e2a83ae1dcfc01a08073a97364dc1119e' and sha(PLAN)=='298deaf0dc7ed9a1068d1dfe75c8b90a9e1c3f8ae0a967f3baa28ff3f87064f1';n=json.loads(SOURCE.read_bytes());pre=ROOT/'packages/campaign/chapter07_predefines/source.v4.reference.json';pr=json.loads(pre.read_bytes());OUT.mkdir(parents=True,exist_ok=True)
 for vid in IDS:
  v=n['variants'][vid];name=v['prefab_key'];p=n['prefabs'][name];effective=[]
  for m in v['modes']:
   node=m['nodes']['_combat'];key=node['raw'].get('_animKey','');hook=m['raw']['_animatorHooker']['m_PathID'];pairs=p['components'][str(hook)]['raw']['_replaceAnimPairs'] if hook else []
   resolved=next((x['toAnimKey'] for x in pairs if x['fromAnimKey']==key),key);effective.append({'mode':m['index'],'raw_key':key,'hook_pointer':hook,'effective_key':resolved,'source_animation':n['animations'][name]['parsed']['animations'].get(resolved),'unhooked_extraction_binding':node.get('animation_binding')})
  keys={c['script_key'] for c in p['components'].values() if c.get('script_key')}
  result={'schema':'ark-sim/ch7-demons-exact-source/v1','variant':v,'source_locks':{str(SOURCE):sha(SOURCE),str(PLAN):sha(PLAN),str(pre):sha(pre)},'prefab':p,'animation':n['animations'][name],'effective_animations':effective,'monoscripts':{k:n['native_monoscripts'][k] for k in keys},'bson_templates':{'empty':n['bson_templates']['templates']['empty'],'ore_buff':pr['bson_templates']['templates']['ore_buff'],'switch_mode_when_trigger':pr['bson_templates']['templates']['switch_mode_when_trigger']},'source_semantics':{'mode_signal':'ore_listener marker, externalore BuffSwitchMode index0/1; notHP/strength threshold','shared_marker_ids':['buff/ch7/source/ore_listener','buff/ch7/source/ore_immune'],'fsm':'Sameactor Behavior statesmode0/mode1; sourceRestartFSM true. Canceloldcasts withtransientgenericcontrol, preserveaccruedattackclock reference untilbody/client evidence','caster':'NeverTrigger/emptycombat neveractivated; actualownedEnemySkills Immo init0/CD5/SP0 independent. .1 internalattackinterval notSkillcadence','visuals':'Effect andeye emptyBuffs visual-only; includeleasedmarkers sourcepaths, notfakecombat effects'},'reference_policies':{'ore_switch':'ExactsourceBSON, actualore producer separateRoot task; controlledpublictransition usedauthorprobe','clock':'NaturalCD5 fromacceptedfinish, mode-specific clocks; FSMrestart preservesaccrued mainattack/cooldown exceptcaster newlyenabledmode init0 reference','timing':'Melee mode0 rawAttack16/full35; mode1 hookAttack_2 actual29/full49. TimeMode0 windup+duration ASPD,min.01reference','empty_visuals':'No gamecombat action inferred from emptytemplate/visualeffectkeys'},'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False};out=OUT/(name+'.source.json');out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'variant':vid,'sha256':sha(out)}))
if __name__=='__main__':main()
