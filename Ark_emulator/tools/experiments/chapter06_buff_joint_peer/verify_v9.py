import sys,json,hashlib,io,contextlib,ast,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v9_candidate';PARENT=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.chapter06_buff_joint_peer import test_peer
OUT=ROOT/'validation/campaign/chapter06_buff_joint_peer_v9';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
FILES=[Path(__file__),Path(test_peer.__file__),ROOT/'tools/experiments/chapter06_buff_joint_peer/test_v9_boundaries.py',ROOT/'tools/experiments/chapter06_buff_joint_peer/test_v7_types.py',ROOT/'tools/experiments/chapter06_buff_joint_peer/test_v9_public_zero.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/candidates/chapter06_buff_join/compose_v5.py',ROOT/'validation/campaign/chapter06_buff_join_v5/composition.json',ROOT/'packages/campaign/chapter06_cold/model.json',ROOT/'packages/campaign/chapter06_cold/source.decoded.json']
FILES += [p for root in [RUNTIME,PARENT] for p in (root/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(set(FILES))}
BEFORE=guard();assert implementation_digest()=='84ccd1edcb7978d37f41be86e0c3d4bf0e877ec30624ef34264bb1998ecea7f4'
changes=[]
for p in (RUNTIME/'ark_sim').rglob('*'):
 if p.is_file() and p.suffix in ['.py','.json']:
  rel=p.relative_to(RUNTIME/'ark_sim');parent=PARENT/'ark_sim'/rel
  if not parent.exists() or sha(parent)!=sha(p):changes.append(rel.as_posix())
assert set(changes)=={'content/compiler.py','content/schemas.py','domains/buff_application.py','domains/buffs.py','domains/effects.py','rules/contracts.json'}
l=json.loads((PARENT/'ark_sim/rules/contracts.json').read_bytes());r=json.loads((RUNTIME/'ark_sim/rules/contracts.json').read_bytes());assert r['contracts'][:-1]==l['contracts'] and r['contracts'][-1]['id']=='buff.application'
for key in set(l)-{'contracts'}:assert l[key]==r[key]
def sets(path):
 tree=ast.parse(path.read_text(encoding='utf8'));return {n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ['EFFECT_FIELDS','DEFAULT_CAPABILITIES','FIELDS']}
left=sets(PARENT/'ark_sim/content/schemas.py');right=sets(RUNTIME/'ark_sim/content/schemas.py');assert left['FIELDS']==right['FIELDS'];assert right['EFFECT_FIELDS']-left['EFFECT_FIELDS']=={'allowed','application_rule'} and left['EFFECT_FIELDS']<=right['EFFECT_FIELDS']
for key,value in left['DEFAULT_CAPABILITIES'].items():assert value<=right['DEFAULT_CAPABILITIES'][key] and right['DEFAULT_CAPABILITIES'][key]-value==({'buff_application'} if key=='effects' else set())
class Plugin:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call':self.rows.append({'nodeid':report.nodeid,'outcome':report.outcome,'duration':report.duration,'failure':str(report.longrepr) if report.failed else None})
plugin=Plugin();buf=io.StringIO()
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):exitcode=pytest.main([str(Path(test_peer.__file__)),str(ROOT/'tools/experiments/chapter06_buff_joint_peer/test_v9_boundaries.py'),str(ROOT/'tools/experiments/chapter06_buff_joint_peer/test_v7_types.py'),str(ROOT/'tools/experiments/chapter06_buff_joint_peer/test_v9_public_zero.py'),'-q'],plugins=[plugin])
after=guard();report={'core':implementation_digest(),'catalog_sha':sha(RUNTIME/'ark_sim/rules/contracts.json'),'changes':changes,'old8fa_unrelated_files_byte_equal':True,'catalog_append_only_buff_application':True,'schema_union_preserved':True,'cases':plugin.rows,'exit':int(exitcode),'output':buf.getvalue(),'guards_before':BEFORE,'guards_after':after,'guards_equal':BEFORE==after,'scope':'Independent generic application hostile plan review and static three-way integration preservation. Synthetic direct-effect tests plus one public-command finite-expiry CP/replay. NoCold author fixture reused, no newstagewhole/primarypromotion.'}
for name,value in [('inputs.json',test_peer.INPUTS),('captures.json',test_peer.CAPTURES),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'pass':sum(x['outcome']=='passed' for x in plugin.rows),'exit':int(exitcode),'guards_equal':BEFORE==after}))
