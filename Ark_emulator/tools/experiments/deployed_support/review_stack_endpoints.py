"""Read-only mathematical audit of already executed Saria stack endpoints."""
import argparse,hashlib,json
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('artifact',type=Path)
parser.add_argument('output',type=Path)
a=parser.parse_args();raw=a.artifact.read_bytes();d=json.loads(raw)
case=next(c for c in d['cases'] if c['case']=='saria_five_layers_atk_and_actual_defense')
assert case['result']=='passed'
hits={e['time']:e['payload']['amount'] for e in case['actual']['events'] if e['type']=='damage.accepted' and e['payload'].get('ability')=='ability/char_202_demkni/normal_attack'}
# Frozen BB interval20/max5/atk.05; base513, synthetic DEF50, normal
# interval1.2=36 ticks and frame17. First post-boundary hit is explicit.
expected={17:463,629:488.65,1205:514.3,1817:539.95,2429:565.6,3005:591.25}
actual={t:hits[t] for t in expected}
assert all(abs(actual[t]-v)<1e-7 for t,v in expected.items())
value={'schema':'ark-sim/executed-event-mathematical-audit/v1','passed':True,'execution_artifact':str(a.artifact),'execution_artifact_sha256':hashlib.sha256(raw).hexdigest(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'implementation_sha256':d['implementation_sha256'],'input_package_sha256':d['input_package_sha256'],'expected':expected,'actual':actual,'scope':'six stack-boundary outgoing packet values in existing command execution; no additional simulation or receipt','formal_approval':False}
a.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
