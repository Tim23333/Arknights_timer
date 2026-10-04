"""Fresh first7 partial model evidence with actual source and fixture guards."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter02_behavior_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import test_models as tests
from ark_sim.adapters.api import implementation_digest
import pytest,UnityPy,ark_sim
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=ROOT/'packages/campaign/chapter02_sources/native.reference.json';d=json.loads(source.read_bytes());matrix=ROOT/'packages/campaign/chapter02_behavior/requirements.reference.json';m=json.loads(matrix.read_bytes())
locks={str(ROOT/k):v for k,v in m['source_locks'].items()}
for p in (Path(__file__),Path(tests.__file__),ROOT/'tools/build_chapter02_behavior_models.py',tests.OUT,matrix):locks[str(p)]=sha(p)
for path,pin in locks.items():assert sha(path)==pin,path
cache={};actual=[]
for key in ('enemy_1005_yokai','enemy_1005_yokai_2','enemy_1017_defdrn','enemy_1500_skulsr'):
 p=d['prefabs'][key];path=ROOT.parent/p['source']['path'];assert sha(path)==p['source']['sha256']
 if path not in cache:cache[path]={o.path_id:o for o in UnityPy.load(str(path)).objects}
 for pid,c in p['components'].items():
  assert cache[path][int(pid)].read_typetree()==c['raw'];actual.append({'owner':key,'component':pid,'class':c['native_class']})
start={p:sha(p) for p in locks};core_start=implementation_digest();assert core_start=='7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe'
code=pytest.main([str(Path(tests.__file__)),'-q']);end={p:sha(p) for p in locks};core_end=implementation_digest()
report={'schema_version':1,'scope':'first7 partial declared source math; not native body/client/stage acceptance','passed':code==0 and start==end and core_start==core_end,'pytest_exit':int(code),'runtime_root':str(RUNTIME),'module_path':ark_sim.__file__,'core_start':core_start,'core_end':core_end,'source_start':start,'source_end':end,'actual_typetrees':actual,'fixtures':tests.INPUTS,'actual_game_correct':False,'formal_approved':False}
out=ROOT/'validation/campaign/chapter02_behavior/first7_final.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'passed':report['passed'],'fixtures':len(tests.INPUTS),'typetrees':len(actual),'output':str(out),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
