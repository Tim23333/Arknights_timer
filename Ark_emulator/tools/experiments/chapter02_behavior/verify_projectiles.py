"""Fresh new-output projectile evidence, independent of frozen first7 report."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter02_behavior_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import test_projectiles as tests
import pytest,UnityPy,ark_sim
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=ROOT/'packages/campaign/chapter02_sources/native.reference.json';d=json.loads(source.read_bytes());matrix=ROOT/'packages/campaign/chapter02_behavior/requirements.reference.json';m=json.loads(matrix.read_bytes());pkg=json.loads(tests.OUT.read_bytes())
locks={str(ROOT/k):v for k,v in m['source_locks'].items()}
for key,pin in pkg['manifest']['metadata']['source_locks'].items():locks[str(ROOT/key)]=pin
for p in (Path(__file__),Path(tests.__file__),ROOT/'tools/build_chapter02_projectile_models.py',tests.OUT,matrix):locks[str(p)]=sha(p)
for path,pin in locks.items():assert sha(path)==pin,path
cache={};actual=[]
for group,keys in (('prefabs',('enemy_1011_wizard','enemy_1028_mocock')),('projectiles',('projectile_enemy_magic_ball','projectile_mocock'))):
 for key in keys:
  p=d[group][key];path=ROOT.parent/p['source']['path'];assert sha(path)==p['source']['sha256']
  if path not in cache:cache[path]={o.path_id:o for o in UnityPy.load(str(path)).objects}
  for pid,c in p['components'].items():assert cache[path][int(pid)].read_typetree()==c['raw'];actual.append({'group':group,'owner':key,'path_id':pid,'class':c['native_class']})
start={p:sha(p) for p in locks};core_start=implementation_digest();assert core_start=='7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe'
code=pytest.main([str(Path(tests.__file__)),'-q']);end={p:sha(p) for p in locks};core_end=implementation_digest()
report={'schema_version':1,'scope':'wizard/mocock real-source projectile parameters, declared 2D math only, not native/stage acceptance','passed':code==0 and start==end and core_start==core_end,'pytest_exit':int(code),'runtime_root':str(RUNTIME),'module_path':ark_sim.__file__,'core_start':core_start,'core_end':core_end,'source_start':start,'source_end':end,'actual_typetrees':actual,'fixtures':tests.INPUTS,'actual_game_correct':False,'formal_approved':False}
out=ROOT/'validation/campaign/chapter02_behavior/projectiles_final.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'passed':report['passed'],'fixtures':len(tests.INPUTS),'typetrees':len(actual),'output':str(out),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
