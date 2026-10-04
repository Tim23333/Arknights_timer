"""Bounded content + canonical-stream checks, with actual predecode input locks."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import test_peer as tests
import ark_sim,pytest,UnityPy
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[Path(__file__),Path(tests.__file__),ROOT/'tools/build_chapter01_m26_content.py',ROOT/'tools/campaign_streaming_evidence.py',ROOT/'tools/run_campaign_streaming_runthrough.py',ROOT/'packages/campaign/actor_selection_source/binding.plan.json',ROOT/'packages/campaign/selector_eligibility/m25.source_profiles.json',ROOT/'packages/campaign/chapter01_behavior/source.reference.json',ROOT/'packages/campaign/chapter01_sources/native.reference.json']
for stage,pin in tests.PINS.items():
 path=ROOT/f'packages/campaign/chapter01_stage_models/m26/level_main_{stage}.partial.json';assert sha(path)==pin;paths.append(path)
 p=json.loads(path.read_bytes())
 for key,pin in p['manifest']['metadata']['source_locks'].items():
  asset=ROOT/key
  if not asset.is_file():asset=ROOT.parent/key
  assert asset.is_file() and sha(asset)==pin,key
  paths.append(asset)
source=json.loads((ROOT/'packages/campaign/chapter01_sources/native.reference.json').read_bytes());asset_record=source['enemies']['enemy_1504_cqbw']['prefab'];asset=ROOT.parent/asset_record['source']['path'];assert sha(asset)==asset_record['source']['sha256'];paths.append(asset)
objects={o.path_id:o for o in UnityPy.load(str(asset)).objects};actual=[]
for pid,row in asset_record['components'].items():
 assert objects[int(pid)].read_typetree()==row['raw'];actual.append({'path_id':pid,'class':row['native_class']})
npc=source['stages']['level_main_01-11']['predefined_prefab_sources']['char_211_adnach'];asset=ROOT.parent/npc['source']['path'];assert sha(asset)==npc['source']['sha256'];paths.append(asset);objects={o.path_id:o for o in UnityPy.load(str(asset)).objects}
for pid,row in npc['components'].items():
 if row['native_class']=='Character':assert objects[int(pid)].read_typetree()==row['raw'];actual.append({'npc_path_id':pid,'class':'Character'})
start={str(p):sha(p) for p in paths};core_start=implementation_digest();assert core_start=='7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe'
code=pytest.main([str(Path(tests.__file__)),'-q']);end={str(p):sha(p) for p in paths};core_end=implementation_digest()
report={'schema_version':1,'scope':'M26 newcontent qualification/math and streaming hash/journal peer only; no stage/native receipt','passed':code==0 and start==end and core_start==core_end,'pytest_exit':int(code),'runtime_root':str(RUNTIME),'module_path':ark_sim.__file__,'core_start':core_start,'core_end':core_end,'source_start':start,'source_end':end,'actual_typetrees':actual,'fixture_inputs':tests.INPUTS,'actual_game_correct':False,'formal_approved':False,'separate_blocker':'streaming runner input identity TOCTOU counterexample under stream_input_identity; this passed report does not discharge that flaw','historical_runs':[{'input_SHA':['3e5aa5e34c37726fe533b743e729e092a28d411ed032a631b669f669a881f389','5915ae0754c50286b9014ed6e5f6cdad2af3d90db275ae1cb69a00909c47a577'],'result':'6passed/3peerfixturefail: second projectile time wrongly assumed distance1 vs actual distance2 arithmetic; empty metadata comparison normalization. Followup predecode hashes rejected changed newcontent; no migrated pass.'}]}
out=ROOT/'validation/campaign/m26_content_peer/final.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'passed':report['passed'],'fixture_inputs':len(tests.INPUTS),'source_locks':len(start),'report_sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
