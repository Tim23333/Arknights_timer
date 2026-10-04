"""Native-life parent, standard life99999 overlay and real fixed12 public plan."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';OUT=ROOT/'validation/campaign/chapter04_10_full_v1';PACKAGE_DIR=ROOT/'packages/campaign/chapter04_stage_models/frost_v5';SCENARIO_DIR=ROOT/'scenarios/campaign/chapter04/level_main_04-10/frost_v5'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.build_campaign_runthrough_input import apply,encoded
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==PIN;old=RUNTIME/'stage/level_main_04-10.complete_frost.explicit.author_prepared.json';assert sha(old)=='7b5c062528c35bbdfe571763ec7065d75b002cf58bb722e760518eac078957d0';original=json.loads(old.read_bytes());native=deepcopy(original);metadata=native['manifest']['metadata'];override=metadata.pop('goal_base_life_authoring');assert override['native']=={'initial':3,'capacity':3} and metadata['native_options']['maxLifePoint']==3;native['scenarioDraft']['resources']['life']=deepcopy(override['native'])
 compare=deepcopy(native);compare['scenarioDraft']['resources']['life']=deepcopy(original['scenarioDraft']['resources']['life']);compare['manifest']['metadata']['goal_base_life_authoring']=override;assert compare==original
 source=PACKAGE_DIR/'level_main_04-10.native_life3.reference.json';overlay=PACKAGE_DIR/'level_main_04-10.life99999.runthrough.json';commands_path=SCENARIO_DIR/'public_fixed12.compact_v1.commands.json';plan_path=SCENARIO_DIR/'public_fixed12.compact_v1.plan.json';receipt=OUT/'prepared.json'
 if any(p.exists() for p in (source,overlay,commands_path,plan_path,receipt)):raise ValueError('Fresh artifacts only')
 PACKAGE_DIR.mkdir(parents=True,exist_ok=True);SCENARIO_DIR.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True);source.write_bytes(encoded(native));run=apply(native,sha(source));overlay.write_bytes(encoded(run));assert run==apply(json.loads(source.read_bytes()),sha(source));Compiler().compile(native);Compiler().compile(run)
 scene=run['scenarioDraft'];defs={d['id']:d for d in run['definitions']};ground_cells=iter([(5,9),(5,8),(5,6),(5,5),(5,4),(5,2)]);high_cells=iter([(4,9),(4,8),(4,7),(4,6),(4,5),(4,4)]);commands=[];operators=[];activation_audit=[]
 for index,uid in enumerate(scene['roster']):
  d=defs[uid];ground=d['components']['deployable']['terrain']=='ground';row,col=next(ground_cells if ground else high_cells);at=index*390;alias='c410_'+uid.rsplit('_',1)[-1];long='amgoat' in uid or 'lisa' in uid or 'kalts' in uid;skill=None
  for aid in d['components']['abilities']:
   a=defs[aid];activation=a.get('activation',{});params={**a.get('parameters',{}),**activation.get('parameters',{})};allowed=activation.get('mode')=='manual' and not params.get('auto_only',False);activation_audit.append({'unit':uid,'ability':aid,'mode':activation.get('mode'),'auto_only':params.get('auto_only',False),'public_manual_allowed':allowed})
   if skill is None and allowed and 'summon' not in aid and 'cannon' not in aid:skill=aid
  commands.append({'at':at,'action':'deploy','entity':uid,'row':row,'col':col,'facing':'right','alias':alias})
  delay=450 if 'plosis' in uid else 750 if 'amgoat' in uid else 451 if 'kalts' in uid else 600 if 'lisa' in uid else 390 if 'weedy' in uid else 150 if 'cgbird' in uid else 300
  if 'kalts' in uid:commands.append({'at':at+30,'action':'skill','source':alias,'ability':'ability/kalts_summon','payload':{'position':{'row':3,'col':2},'facing':'right'}});delay=481
  if skill:commands.append({'at':at+delay,'action':'skill','source':alias,'ability':skill})
  commands.append({'at':at+delay+60 if long or 'plosis' in uid or 'weedy' in uid else at+360,'action':'withdraw','source':alias});operators.append({'unit':uid,'alias':alias,'terrain':d['components']['deployable']['terrain'],'cell':{'row':row,'col':col},'base_cost':d['components']['attributes']['base']['deploy_cost'],'selected_manual_skill':skill,'deploy_at':at,'skill_at':at+delay if skill else None})
 commands.sort(key=lambda c:c['at']);commands_path.write_bytes(encoded(commands));plan={'operators':operators,'commands':commands,'activation_audit':activation_audit,'source_seed':scene['seed'],'initial_DP':10,'native_slots':10,'fixed_roster':12,'first12_window':[0,4290],'base_only_overlay':'Standard build_campaign_runthrough_input.apply; actors/combat/DP/timeline/map/slots/seed unchanged','operation_policy':'Real deployment costs and natural resource recovery; attempts may legitimately fail due to freeze/controlled/dead/insufficient-resource states. Record all outcomes; no value grants.','owned_summon':'Actual kalts_summon public payload terrain at3,2,10DP, then wait15s+one logic tick for hostS3; no fabricated target or SP','dynamic_tile_policy':'Base legal cells; real frozen-floor occupancy remains authoritative during execution','full_stage_executed':False};plan_path.write_bytes(encoded(plan))
 result={'core':PIN,'original_author_prefix_stage':str(old),'original_author_stage_sha':sha(old),'source_package':str(source),'source_sha':sha(source),'source_native_life':native['scenarioDraft']['resources']['life'],'overlay_package':str(overlay),'overlay_sha':sha(overlay),'standard_overlay_builder':str(ROOT/'tools/build_campaign_runthrough_input.py'),'standard_overlay_builder_sha':sha(ROOT/'tools/build_campaign_runthrough_input.py'),'commands':str(commands_path),'commands_sha':sha(commands_path),'plan':str(plan_path),'plan_sha':sha(plan_path),'native_restoration_only':['scenarioDraft.resources.life','manifest.metadata.goal_base_life_authoring removal'],'overlay_exact_standard_apply':True,'born':43,'variants':7,'native_DP':10,'native_slots':10,'native_move_multiplier':.5,'source_seed':14705740,'first12_last_deploy':4290,'full_stage_executed':False}
 receipt.write_bytes(encoded(result));assert sha(old)=='7b5c062528c35bbdfe571763ec7065d75b002cf58bb722e760518eac078957d0';print(json.dumps(result))
if __name__=='__main__':main()
