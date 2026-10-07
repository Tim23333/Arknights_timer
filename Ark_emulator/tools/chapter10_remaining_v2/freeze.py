"""Pin joint-runtime author regression and real lord source bridge."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter10_remaining_v2.build import build,SOURCE
OUT=ROOT/'validation/campaign/chapter10_remaining_v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':str(p.resolve()),'sha256':sha(p),'bytes':p.stat().st_size}
def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists()
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
core=implementation_digest();assert core=='9a7d4a01b7fe0a8d77a39e4b280b330e65670349b6fb2716c1319dabcc491ed9'
reports=[]
for name in ['author.bloodline.joint.v1.json','domain46.joint.v1.json','integration.actual.v6.json']:
    path=OUT/name;r=json.loads(path.read_bytes())
    assert r['actual_exit']==0 and r['source_equal'] and r['core_before']==r['core_after']==core
    assert all(sha(Path(p))==h for p,h in r['source_after'].items())
    reports.append(pin(path))
module=ROOT/'packages/campaign/chapter10_consumers/remaining_v2/module.enemy_1226_dklord_2.v2.json'
write(module,build())
receipts=[]
for name in ['chapter10_bloodline_joint_author_v1','chapter10_bloodline_joint_domain46_v1',*[f'chapter10_remaining_v2_integration_v{i}' for i in range(1,7)]]:
    p=Path('E:/ArkSimLogs/receipts')/name/'completion.json';r=json.loads(p.read_bytes())
    assert r['cleanup_exit']==0 and r['raw_logs_removed_after_validation']
    receipts.append({**pin(p),'worker_exit':r['worker_exit'],'cleanup':r['cleanup_result']})
inventory={str(p.relative_to(CAND)).replace('\\','/'):sha(p) for p in sorted((CAND/'ark_sim').rglob('*')) if p.is_file() and p.suffix in ['.py','.json']}
write(OUT/'freeze.v2.json',{'schema':'ark-sim/source-bridge-freeze/v2','candidate':str(CAND),'core':core,'status':'fresh_author_regression_and_source_bridge_passed_independent_integration_pending',
    'candidate_inventory':inventory,'source_module':pin(module),'source_inputs':[pin(SOURCE),pin(ROOT/'packages/campaign/chapter10_source_prepare/enemies.native.v1.json'),pin(ROOT/'packages/campaign/chapter10_source_prepare/bson.transitive.v2.json')],
    'helpers':[pin(p) for p in sorted(Path(__file__).parent.glob('*.py'))]+[pin(ROOT/'tools/chapter10_remaining_v1/build.py'),pin(ROOT/'tools/chapter10_bloodline_v1/build.py')],
    'reports':reports,'groups':{'bloodline_author':7,'original_domain':46,'lord_integration':1},'cleanup':receipts,'deleted_bytes':sum(r['cleanup']['reclaimed_bytes'] for r in receipts),'remaining_raw':0,'errors':0,
    'bridge_interface':'tools.chapter10_remaining_v2.build.build(key=enemy_1226_dklord_2), providers(); module includes six actual source bloodline bodies, actual MARK/DEATH rules; bind_recipients wraps original explicit attribute rules.',
    'source_semantics':{'lord':'nativeHP20000/ATK1200, reverse-source aura .25 per valid bloodsucker cap6; death key enemy_1221_dzomg_2/delay1; source Buff owner caller validated by finite death contract','test':'Actual kill7/pending8/cp19/born37/end43, original wave0/absolute WAIT90, keeper retained alive; both real aura removal and immediate parent kill verified','CPP':'Full checkpoint equality including retained low-level tick3 attribute query','head':'Full public-command replay equality on independent fresh run without low-level query'},
    'preserved_failures':[pin(p) for p in sorted(OUT.glob('integration.*.json')) if p.name!='integration.actual.v6.json'],'prior_bloodline_freeze':pin(ROOT/'validation/campaign/chapter10_bloodline_v1/final.freeze.v1.json'),
    'runtime_changed':False,'primary_changed':False,'client_verified':False,'long_suite_started':False})
print(json.dumps({'freeze':pin(OUT/'freeze.v2.json'),'module':pin(module),'core':core,'deleted_bytes':sum(r['cleanup']['reclaimed_bytes'] for r in receipts)},indent=2))
