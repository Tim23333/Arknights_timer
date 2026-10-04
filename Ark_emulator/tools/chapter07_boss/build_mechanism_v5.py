"""Reproduce v5 fixed-profile adapter; preserve parent builder provenance."""
from pathlib import Path
import json
from tools.chapter07_boss.build_mechanism_v1 import OUT,sha
def main():
 old=OUT/'mechanism.v4.json'
 if sha(old)!='8feed8c919a373504d04d3af017670469dff1866d945bbb21bce3a137e615bd6':raise ValueError('Exact v4 input required')
 p=json.loads(old.read_bytes());p['projectiles'][0]['motion']['parameters']['mode']='fixed';p['manifest']['metadata']['trajectory_profile_adapter']='Generic existing fixed profile isstationary carrier; fixedexpiry0.5 nativeflag reference, v4 unknownstationary API name retainedfailure';p['manifest']['id']='package/ch7/patrt/partial_mechanism_v5';out=OUT/'mechanism.v5.json';data=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode()
 if out.exists() and out.read_bytes()!=data:raise ValueError('Do not overwrite changed v5 artifact')
 if not out.exists():out.write_bytes(data)
 print(json.dumps({'sha256':sha(out),'derivative_builder':str(Path(__file__)),'stage_export_allowed':False}))
if __name__=='__main__':main()
