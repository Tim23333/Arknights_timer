import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';PARENT=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter06_boss_peer import test_multi_source_frozen as multi, test_actual_npc_area as npc
from tools.experiments.chapter06_boss_peer import test_source_final_fixture as records
OUT=ROOT/'validation/campaign/chapter06_source_area_independent';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(multi.__file__),Path(npc.__file__)];files=tests+[Path(records.__file__),Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/campaign_content_composition_v2.py',ROOT/'tools/chapter06_review/runner_providers_v1.py',ROOT/'tools/chapter06/cold/policies.py',ROOT/'tools/chapter06_npcs/providers_v2.py',ROOT/'tools/chapter06_npcs/policies.py',ROOT/'tools/chapter06_npcs/huang_v6_policy.py',ROOT/'tools/chapter06_npcs/amiya_policy.py',ROOT/'packages/campaign/chapter06_boss/frstar2_v4/model.json',ROOT/'packages/campaign/chapter06_boss/frstar2_s_v3/model.json',ROOT/'packages/campaign/chapter06_boss/frstar2/source.closure.json',ROOT/'packages/campaign/chapter06_plans/source.plan.json',ROOT/'packages/campaign/chapter06_npcs/amiya.v3.model.json',ROOT/'packages/campaign/chapter06_npcs/swllow.v2.model.json',ROOT/'packages/campaign/chapter06_npcs/huang.v7.model.json',ROOT/'packages/campaign/chapter06_cold/model.json',ROOT/'packages/campaign/chapter06_predefines_consumer/module.v2.reference.json',ROOT/'validation/campaign/content_base_integration_freeze_v1/freeze.json']+[p for r in [RUNTIME,PARENT] for p in (r/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
for folder in ['frstar2_v4','frstar2_s_v3']:
 pinfile=ROOT/'packages/campaign/chapter06_boss'/folder/'delivery.pins.json';files.append(pinfile);body=json.loads(pinfile.read_bytes());files.extend(ROOT/p for p in body['pins'])
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='d509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1'
changes=[p.relative_to(RUNTIME/'ark_sim').as_posix() for p in (RUNTIME/'ark_sim').rglob('*.py') if sha(p)!=sha(PARENT/'ark_sim'/p.relative_to(RUNTIME/'ark_sim'))];assert set(changes)=={'domains/buff_application.py','domains/buffs.py','domains/no_source_damage.py','domains/tile_targets.py'}
class Plugin:
 def __init__(self):self.rows=[]
 def pytest_runtest_teardown(self,item,nextitem):
  tmp=item.funcargs.get('tmp_path')
  if tmp:
   folder=OUT/'actual_ordered_cps'/item.name;folder.mkdir(parents=True,exist_ok=True)
   for p in tmp.glob('*.json'):(folder/p.name).write_bytes(p.read_bytes())
 def pytest_runtest_logreport(self,report):
  if report.when=='call':self.rows.append({'nodeid':report.nodeid,'outcome':report.outcome,'duration':report.duration,'failure':str(report.longrepr) if report.failed else None})
plugin=Plugin();buf=io.StringIO()
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(t) for t in tests),'-q','--import-mode=importlib'],plugins=[plugin])
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'changed_files':changes,'scope':'New source3513/5184 on d509. Four fresh3target cases onearea three distinctMRES packets; one prefrozen doubles only its hit and no doublecache amplification; two actualsourceNPCs all originalE2L25/locations/facing/hiddenregistration publicactivated,0slots, onepacket+oneCold each with true preimpactdiskCP/head. Reference sourceTimeMode1 fixed and normalSourceTimeMode0/scaling remain declaredpolicy; no original whole/client/nativecoroutine claim.'}
for name,value in [('inputs.json',records.INPUTS+npc.INPUTS),('captures.json',records.CAPTURES+npc.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
primitive=[r for r in plugin.rows if '/test_self_remove.py' in r['nodeid']];assert len(plugin.rows)==6
with (OUT/'primitive_verification.json').open('x',encoding='utf8') as f:json.dump({'core':report['core'],'cases':primitive,'guards_equal':before==after,'report_sha':sha(OUT/'verification.json'),'changed_files':changes,'no_other_primitive_exemption':True},f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'primitive_sha':sha(OUT/'primitive_verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
