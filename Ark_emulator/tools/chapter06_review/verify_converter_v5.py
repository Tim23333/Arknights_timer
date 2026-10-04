import sys,json,hashlib,io,contextlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.chapter06_review.story_keys_v5 import convert,digest,SCHEMA,POLICY
OUT=ROOT/'validation/campaign/chapter06_review/converter_v5_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[ROOT/'tools/build_reference_stage_scenario_v4.py',ROOT/'tools/build_reference_stage_scenario_v3.py',ROOT/'tools/build_reference_stage_scenario_v2.py',ROOT/'packages/campaign/native_reference/level_main_06-15.json',ROOT/'packages/campaign/native_reference/level_main_05-09.json',ROOT/'packages/campaign/native_reference/level_main_05-10.json']+list(Path(__file__).parent.glob('*v5.py'))+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
class Results:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  r=report
  if r.when=='call':self.rows.append({'nodeid':r.nodeid,'outcome':r.outcome,'duration':r.duration,'failure':str(r.longrepr) if r.failed else None})
plugin=Results();buf=io.StringIO()
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([str(ROOT/'tools/chapter06_review/test_story_keys_v5.py'),'-q'],plugins=[plugin])
native=json.loads((ROOT/'packages/campaign/native_reference/level_main_06-15.json').read_bytes());definitions={r['inst']['characterKey']:'unit/proposed/'+r['inst']['characterKey']+'/source_config' for r in native['predefines']['characterInsts']}
profile={'schema':SCHEMA,'policy':POLICY,'native_id':'level_main_06-15','native_document_digest':digest(native),'bindings':[{'bucket':'characterInsts','index':i,'activation_key':r['inst']['characterKey'],'definition':definitions[r['inst']['characterKey']]} for i,r in enumerate(native['predefines']['characterInsts'])]}
converted=convert(native,'level_main_06-15',definitions,story_key_profile=profile)
for name,data in [('actual_source_mapping_profile.json',profile),('pure_converted_predefines.json',converted)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
after=guard();report={'core':implementation_digest(),'pytest_exit':int(code),'cases':plugin.rows,'output':buf.getvalue(),'before':before,'after':after,'guards_equal':before==after,'v4_parent_sha':sha(ROOT/'tools/build_reference_stage_scenario_v4.py'),'converter_sha':sha(ROOT/'tools/chapter06_review/stage_converter_v5.py'),'story_key_helper_sha':sha(ROOT/'tools/chapter06_review/story_keys_v5.py'),'pure_mapping_sha':sha(OUT/'pure_converted_predefines.json'),'source_profile_sha':sha(OUT/'actual_source_mapping_profile.json'),'scope':'Author pure converter validation with proposed definition IDs. No6-17special spawn accounting consumed, noNPC combat definitions compiled, no whole-stage run and no parent/core modification. Existing C5v4 output equivalence checked for both5-9/5-10 on exact source projection with branches handled separately.'}
with (OUT/'verification.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'tests':len(plugin.rows),'exit':int(code),'guards_equal':before==after,'sha':sha(OUT/'verification.json'),'converter_sha':report['converter_sha'],'helper_sha':report['story_key_helper_sha']}))
