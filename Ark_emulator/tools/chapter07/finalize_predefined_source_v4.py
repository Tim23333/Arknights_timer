"""Append exact consumed v3/local-reader pins, preserving old source identities."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];parent=ROOT/'packages/campaign/chapter07_predefines/source.v3.reference.json';out=parent.with_name('source.v4.reference.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
v=json.loads(parent.read_bytes());assert not out.exists();v['parent_source']={'path':parent.relative_to(ROOT).as_posix(),'sha256':sha(parent)}
for p in (ROOT/'tools/chapter07/build_predefined_sources_v3.py',ROOT/'tools/chapter07/native_assets_v1.py',Path(__file__)):
 v['source_locks'][p.relative_to(ROOT.parent).as_posix()]=sha(p)
v['source_policy_notes']=['Fixed56aee table/source plans, local20260831 skills/BSON/story and official20250327 entity tokens are separate pinned versions. No asset/table/client alignment is asserted.','Referenced ScriptableObjects with native m_GameObject.PathID0 remain null; raw component/PPtr/MonoScript preserved, never fabricated GameObject.','7-18 ore native alias null and fifteen mine cards remain original. No runtime activation/card/mine behavior accepted here.']
assert all(sha(ROOT.parent/n)==h for n,h in v['source_locks'].items());out.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'locks':len(v['source_locks'])}))
