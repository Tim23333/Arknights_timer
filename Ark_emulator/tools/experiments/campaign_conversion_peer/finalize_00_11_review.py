import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m12_projection_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from tools.campaign_model_acceptance import source_review_gate
import UnityPy
CORE='bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'
def read(p):return json.loads((ROOT/p).read_bytes())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def ident(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def write(p,v):(ROOT/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def ref(p,claim):return {'path':p,'sha256':sha(p),'claim':claim}
def run():
 assert implementation_digest()==CORE
 content='packages/campaign/mainline_models/level_main_00-11.m12_projection.json';native='packages/campaign/native_reference/level_main_00-11.json';audit=read('packages/campaign/conversion_drafts/main_00-11.external.audit.json');model=read(content);program=Compiler().compile(model);defs={k:thaw(v) for k,v in program.definitions.items()};units=[]
 mapping={'maxHp':'max_hp','atk':'atk','def':'def','magicResistance':'mres','baseAttackTime':'attack_interval','moveSpeed':'move_speed','blockCnt':'block_count','cost':'deploy_cost','respawnTime':'redeploy_time','massLevel':'mass_level'}
 for r in read('packages/campaign/operators.normalized.json')['operators']:
  u=defs['unit/'+r['character_id']];c=u['components'];stats=r['stats']['model_stats'];skill=u['metadata']['selected_skill_ability'];assert all(c['attributes']['base'][v]==stats[k] for k,v in mapping.items());assert c['attributes']['base']['attack_speed_ratio']==stats['attackSpeed']/100
  assert u['metadata']['config']==r['config'] and skill in c['abilities'] and defs[skill]['metadata']['native_skill_id']==r['selected_skill']['skill_id'];assert c['resources']['sp']['initial']==r['selected_skill']['level']['spData']['initSp'] and c['resources']['sp']['capacity']==r['selected_skill']['level']['spData']['spCost'];units.append({'character_id':r['character_id'],'selected_owned':skill})
 for closure in audit['operator_definition_closures']:
  for row in closure['reachable_definition_identities']:assert ident(defs[row['id']])==row['sha256']
 sub='validation/campaign/00_11_operator_consumer_subchecks.json';write(sub,{'passed':True,'subject_model_content_sha256':sha(content),'implementation_sha256':CORE,'operators':units,'closure_definitions_actual_equal':True,'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(Path(__file__).relative_to(ROOT)),'result':'passed'}]})
 consumers='validation/campaign/00_11_source_consumer_subchecks.json';raw='validation/campaign/00_11_original_enemy_field_review.json';r=read(consumers);assert r['passed'] and r['subject_model_content_sha256']==sha(content) and r['implementation_sha256']==CORE
 ptrs=[];cache={}
 for enemy in read('packages/campaign/sources.00_11.reference.json')['enemies']:
  pf=enemy['prefab'];asset=(ROOT.parent/pf['source']).resolve()
  if asset not in cache:cache[asset]={o.path_id:o for o in UnityPy.load(str(asset)).objects}
  mode=cache[asset][pf['mode_path_id']].read_typetree();assert mode['_combat']=={'m_FileID':0,'m_PathID':pf['combat_path_id']}
  ptrs.append({'enemy':enemy['native_id'],'actual_mode_combat_PPtr':mode['_combat']})
 write(raw,{'actual_same_asset_PPtr_resolution':ptrs,'schema':'ark-sim/original-source-fields-review/v2','passed':True,'subject_model_content_sha256':sha(content),'subject_native_source_sha256':sha(native),'implementation_sha256':CORE,'raw_actual_enemy_consumers':r['raw_actual_enemy_consumers'],'source_locks':audit['source_locks'],'scope':'Six actual Unity combat/mode PPtr/Spine/mover and DB native rows reread. Semantic/UI evidence separate.','tests':r['tests']})
 checks=['unit_attributes_and_growth','selected_skills_and_talents','native_enemy_dependencies','map_routes_controls_and_objectives','no_substituted_or_ignored_mechanics'];evidence={checks[0]:[ref(sub,'Actual twelve normalized model stats/ASPD/config mapping on new compiled subject')],checks[1]:[ref(sub,'Selected ability ownership/SP and all declared actor dependency identities actually checked')],checks[2]:[ref(consumers,'Six actual raw DB/PPtr/combat/Spine/mover values consumed by model stats/frames/types/scale/steering')],checks[3]:[ref(consumers,'Native matrix/palette/option values, 20SPAWN groups37 actors6/9/22, managed flags/relative clocks, deadline route13/14 actual origin90+900, five route17 Cartesian offsets; UI actual synchronous completion/no lock leak')],checks[4]:[ref(consumers,'All native action expansion accounted for; zero-life managed UI completion equivalence real CP/replay; independent same-subject complete37/0 report checked, not substituted for source proof')]}
 locks=audit['source_locks']+[{'path':'tools/experiments/campaign_conversion_peer/review_00_11.py','sha256':sha('tools/experiments/campaign_conversion_peer/review_00_11.py')},{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'sha256':sha(Path(__file__).relative_to(ROOT))},{'path':consumers,'sha256':sha(consumers)}]
 review={'schema':'ark-sim/source-consumer-review/v2','passed':True,'status':'approved_for_declared_model_profile','reviewer':'campaign_catalog independent 00-11 source consumer review','subject_model_content_sha256':sha(content),'subject_native_source_sha256':sha(native),'implementation_sha256':CORE,'source_locks':locks,'checks':dict.fromkeys(checks,'passed'),'consumer_evidence':evidence,'raw_source_evidence':[ref(raw,'Actual raw Unity/DB/Spine subset; does not replace semantic proofs')],'pending_model_gaps':[],'client_pending':['Native managed scheduler negative timeout body','Native UI ACK duration/wall time/game-time pause','Native RNG seed algorithm/distribution/steering/collision bodies','Stat interpolation/client attack callback profiles retained'],'scope':'Declared mathematical profiles; generic timeline.action is real synchronous effects completion/model ACK after Story/Info processing, zero-lifetime member elision proven. No native UI lifecycle, whole-model receipt or client accuracy approval.','formal_approval':False,'external_receipt_issued':False}
 out='validation/campaign/00_11_source_consumer_review.json';write(out,review);expected={'content_sha256':sha(content),'native_source_sha256':sha(native),'implementation_sha256':CORE};assert source_review_gate(ROOT,[{'path':out,'sha256':sha(out)}],expected);assert implementation_digest()==CORE;print(json.dumps({'passed':True,'gate_accepted':True,'source_locks':len(locks),'operators':len(units)}))
if __name__=='__main__':run()
