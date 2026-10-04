"""Explicit new-root/package adapter; prior helper bytes and reports stay frozen."""
import hashlib
import json
import sys
import types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m20_dormant_source_candidate'
CORE='b506ee18e7137c3658f1fe8ce77b4b612bf48bceb9b02446f2dfcb7d91abbf0d'
PACKAGE=ROOT/'packages/campaign/chapter01_stage_models/m20_source/level_main_01-11.dormant.partial.json'
PACKAGE_SHA='52a7432cc87e3806afd6d63c7a1fd2f06782caf34bdebde4cbc176b9ea7c7111'
sys.path.insert(0,str(RUNTIME))
import ark_sim
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
sys.path.append(str(ROOT))
OUT=ROOT/'validation/campaign/m20_source_peer';OUT.mkdir(parents=True,exist_ok=True)
loaded={};adapters=[]
def read_locked(path,expected=None):
    raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if expected is not None:assert sha==expected,str(path)
    loaded[str(path)]=sha
    return raw
package=json.loads(read_locked(PACKAGE,PACKAGE_SHA)) # bytes hashed before decode
def load_old(name,filename,replacements=()):
    path=ROOT/'tools/experiments/m20_peer'/filename;raw=read_locked(path);text=raw.decode('utf8')
    for before,after in replacements:
        assert text.count(before)==1,(filename,before)
        text=text.replace(before,after,1)
        adapters.append({'path':str(path),'old':before,'new':after,'original_sha256':hashlib.sha256(raw).hexdigest(),
           'adapter_source_sha256':hashlib.sha256(text.encode()).hexdigest(),'changes':'bootstrap/runtime or input builder only; behavior expectations untouched'})
    module=types.ModuleType(name);module.__file__=str(path);module.__package__='tools.experiments.m20_peer';sys.modules[name]=module
    exec(compile(text,str(path),'exec'),module.__dict__)
    return module
h=load_old('tools.experiments.m20_peer.probe','probe.py',[("'unpack_work/campaign_m20_dormant_candidate'","'unpack_work/campaign_m20_dormant_source_candidate'")])
b=load_old('tools.experiments.m20_peer.behavior_probe','behavior_probe.py')
r=load_old('tools.experiments.m20_peer.revised_review','revised_review.py',[
  ('from tools.build_chapter01_dormant_model import build,OUT,SOURCE',
   'from tools.build_chapter01_dormant_source_model import build,OUT\n    from tools.build_chapter01_dormant_model import SOURCE')])
s=load_old('tools.experiments.m20_peer.source_boundary','source_boundary.py')
for path in [Path(__file__),ROOT/'tools/build_chapter01_dormant_source_model.py',ROOT/'tools/build_chapter01_dormant_model.py',
  ROOT/'packages/campaign/chapter01_predefines/native.reference.json',ROOT.parent/'unpack_work/campaign_tables/range_table.reference_56a.json',
  RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json']:
    read_locked(path)
reference=json.loads(read_locked(ROOT/'packages/campaign/chapter01_predefines/native.reference.json'))
read_locked(ROOT.parent/reference['prefab']['source']['path'],reference['prefab']['source']['sha256'])
for path,pin in package['manifest']['metadata']['source_locks'].items():read_locked((ROOT/path).resolve(),pin)
start=dict(loaded);fixtures=[];current=None;number=0
original_make=h.make
def actual_make(data):
    global number
    number+=1;path=OUT/'fixtures'/f'{number:02d}_{current}.input.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
    actual=read_locked(path);input_sha=hashlib.sha256(actual).hexdigest();sim=original_make(json.loads(actual))
    fixtures.append({'case':current,'path':str(path),'sha256_before_decode':input_sha,'program':sim.program.fingerprint,
      'runtime':sim.runtime_fingerprint,'actual_runtime_module':ark_sim.__file__})
    return sim
h.make=actual_make
cases=[]
functions=[('original_SP',h.inactive_direct_sp),('original_freeze',h.inactive_snapshot_freeze),('original_behavior',b.case),
 ('registration_lifetime',h.registration_is_not_alias_and_lifetime_starts_at_activation),('double_paid',h.double_activation_rolls_back_public_paid_command),
 ('direct_behavior',r.direct_behavior_boundary),('late_activation_snapshot',r.late_activation_emission_snapshot),
 ('generic_inactive_target',r.generic_inactive_effects_do_not_write_schedule_or_sample),('native_NPC_capacity',r.native_wrapper_capacity_and_source_equal),
 ('inactive_source_SP',lambda:s.source_write('sp')),('inactive_source_damage',lambda:s.source_write('damage')),
 ('inactive_source_RNG',lambda:s.source_write('random')),('genuine_retired_packet',s.real_launched_packet_survives_opt_in_source_death)]
for current,fn in functions:
    h.LAST=None
    try:fn();c={'case':current,'result':'passed'}
    except Exception as error:c={'case':current,'result':'failed','error':repr(error)}
    if h.LAST is not None:
        sim=h.LAST;c.update({'program':sim.program.fingerprint,'runtime':sim.runtime_fingerprint,'commands':sim.export_replay(),
         'snapshot':sim.snapshot(),'events':[thaw(e) for e in sim.session.events]})
    cases.append(c)
end={path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in loaded}
stable=all(end[p]==v for p,v in start.items()) and all(end[f['path']]==f['sha256_before_decode'] for f in fixtures) and implementation_digest()==CORE
passed=stable and all(c['result']=='passed' for c in cases)
value={'schema':'ark-sim/dormant-source-peer-review/v1','passed':passed,'formal_approval':False,'review_receipt':False,
 'core_at_start':CORE,'core_at_completion':implementation_digest(),'runtime_module':ark_sim.__file__,'package_path':str(PACKAGE),
 'package_sha256_before_decode':PACKAGE_SHA,'source_at_start':start,'source_at_completion':end,'identity_stable':stable,
 'helper_adapters':adapters,'fixture_inputs':fixtures,'cases':cases,'scope':'13 independent dormant boundaries; no full stage/native receipt; NPC capacity does not prove SP aura'}
(OUT/'final.json').write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({'passed':passed,'core':CORE,'package':PACKAGE_SHA,'fixtures':len(fixtures),
  'cases':[{k:v for k,v in c.items() if k in ('case','result','error')} for c in cases]}))
raise SystemExit(0 if passed else 1)
