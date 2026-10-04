import sys,json,hashlib,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';PARENT=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter06_boss_peer import test_story_timer as story

OUT=ROOT/'validation/campaign/chapter06_story_timer_independent';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(story.__file__)];files=tests+[Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/campaign_content_composition_v2.py',ROOT/'tools/chapter06_review/runner_providers_v1.py',ROOT/'tools/chapter06/cold/policies.py',ROOT/'tools/chapter06_npcs/providers_v2.py',ROOT/'tools/chapter06_npcs/policies.py',ROOT/'tools/chapter06_npcs/huang_v6_policy.py',ROOT/'tools/chapter06_npcs/amiya_policy.py',ROOT/'packages/campaign/chapter06_boss/frstar2_v4/model.json',ROOT/'packages/campaign/chapter06_boss/frstar2_s_v3/model.json',ROOT/'packages/campaign/chapter06_boss/frstar2/source.closure.json',ROOT/'packages/campaign/chapter06_plans/source.plan.json',ROOT/'packages/campaign/chapter06_npcs/amiya.v3.model.json',ROOT/'packages/campaign/chapter06_npcs/swllow.v2.model.json',ROOT/'packages/campaign/chapter06_npcs/huang.v7.model.json',ROOT/'packages/campaign/chapter06_cold/model.json',ROOT/'packages/campaign/chapter06_predefines_consumer/module.v2.reference.json',ROOT/'validation/campaign/content_base_integration_freeze_v1/freeze.json']+[p for r in [RUNTIME,PARENT] for p in (r/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
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
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'changed_files':changes,'scope':'Fresh actual5184_s HP95000 stationary/nonbuildable controlled fixture, source first30 then48*2000 cadence/final1000@1440 deathonce actorfreeBUFF withoutModifyTrue/no SP or actorcast, true orderedCP31 and publichead/alltrace. Separate from actualwhole1145routeexit; no whole/client/bodycoroutine claim.'}
for name,value in [('inputs.json',story.INPUTS),('captures.json',story.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
primitive=[r for r in plugin.rows if '/test_self_remove.py' in r['nodeid']];assert len(plugin.rows)==1
with (OUT/'primitive_verification.json').open('x',encoding='utf8') as f:json.dump({'core':report['core'],'cases':primitive,'guards_equal':before==after,'report_sha':sha(OUT/'verification.json'),'changed_files':changes,'no_other_primitive_exemption':True},f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'primitive_sha':sha(OUT/'primitive_verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
