from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m38_integrated_candidate';sys.path.insert(0,str(RUNTIME))
import ark_sim
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
sys.path.insert(0,str(Path(__file__).parent));import test_model as t
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';core=implementation_digest();assert core=='2165e5e267fa62012867d7676e0ad68f53234217e0b62fec31ace3956f23fdd6'
p=t.fixture();s=t.make(p);t.cmd(s,'director','silence',0);t.cmd(s,'director','unsilence',1);t.cmd(s,'director','shot',1);s.advance(2)
hits=[thaw(e) for e in s.session.events if e['type']=='damage.accepted'];assert hits[0]['payload']['amount']==900
out=ROOT/'validation/campaign/defdrn_status/remove_history_m38';out.mkdir(parents=True,exist_ok=True);report={'core_start':core,'core_end':implementation_digest(),'module':ark_sim.__file__,'fixture':t.INPUTS[-1],'commands':s.export_replay()['commands'],'expected_sameframe_damage':600,'actual':hits,'events':thaw(s.session.events),'scope':'new declared synchronous aura status gate, source policy unchanged','formal_approved':False};(out/'counterexample.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(out/'buffs.py').write_bytes((RUNTIME/'ark_sim/domains/buffs.py').read_bytes());(out/'test_model.py').write_bytes(Path(t.__file__).read_bytes());print(json.dumps({'core':core,'actual':900,'expected':600}))
