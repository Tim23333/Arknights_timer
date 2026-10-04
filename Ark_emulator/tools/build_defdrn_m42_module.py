"""New runtime-bound module metadata; original source/math definitions identical."""
from pathlib import Path
import argparse,json,hashlib
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT/'packages/campaign/chapter02_units/defdrn.status.model.json';OUT=ROOT/'packages/campaign/chapter02_units/defdrn.status.m42.model.json';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();PIN='bf2633f9b24833f21782fae40990912cbac896990e3d84ad8b6caaff522b986b'
def build():
 assert sha(PARENT)==PIN;p=json.loads(PARENT.read_bytes());p['manifest']['metadata'].update(required_runtime='2746020dd269241d8802551ea63cb28243755ff0105a19bb09033c448f497420',parent_status_module_sha256=PIN,runtime_binding_builder_sha256=sha(__file__),synchronous_remove_model=True);p['manifest']['metadata']['source_locks']['packages/campaign/chapter02_units/defdrn.status.model.json']=PIN;return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode()
 if a.check:assert OUT.read_bytes()==b
 else:OUT.write_bytes(b)
 print(json.dumps({'passed':True,'check':a.check,'sha256':sha(OUT)}))
