"""Effective-instance ability override defeats static source declaration."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m31_tile_field_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/m31_roster_peer';p=json.loads((OUT/'static_route.fixture.json').read_bytes());p['entities'][0]['components']['spatial']={};p['entities'][1]['components']['attributes']['base'].update({'def':0,'mres':0})
p['abilities']=[{'id':'ability/illegal_field_attack','kind':'ability','activation':{'mode':'manual'},'selector':'selector/player','timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}]
p['selectors'].append({'id':'selector/player','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}],'limit':1})
p['scenarioDraft']['initialEntities'].append({'definition':'unit/static_field','instanceAlias':'field_clone','position':{'row':0,'col':0},'components':{'abilities':['ability/illegal_field_attack'],'attributes':{'base':{'atk':50}}}})
raw=(json.dumps(p,indent=2)+'\n').encode();(OUT/'static_override.fixture.json').write_bytes(raw);core=implementation_digest();assert core=='7720452f53f4e8b1e0c3e2ba77ab03e0b0b8e8e3b2cdfabf79fe9499f967e96d'
s=Engine.create(Compiler().compile(json.loads(raw)),seed=3105);s.submit({'action':'skill','source':'field_clone','ability':'ability/illegal_field_attack'},at=0);s.advance(1)
hits=[thaw(e) for e in s.session.events if e['type']=='damage.accepted'];report={'core_start':core,'core_end':implementation_digest(),'fixture_bytes_sha256':hashlib.sha256(raw).hexdigest(),'fixture':p,'expected_compile_or_command_rejection':True,'actual_command_accepted':[thaw(e) for e in s.session.events if e['type']=='command.accepted'],'actual_damage':hits,'counterexample_reproduced':len(hits)==1 and hits[0]['payload']['amount']==50,'events':thaw(s.session.events),'formal_approved':False}
(OUT/'static_override.counterexample.final.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'counterexample_reproduced':report['counterexample_reproduced'],'damage':hits[0]['payload']['amount'] if hits else None}));raise SystemExit(0 if report['counterexample_reproduced'] else 1)
