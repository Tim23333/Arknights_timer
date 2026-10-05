import sys,os,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str((ROOT/'../unpack_work/campaign_c9_finale_joint_v1_candidate').resolve()));sys.path.insert(1,str(ROOT))
from tools.chapter09_stage919_wave_v4.test_wave import create,OUTPUT,CORE
from ark_sim.contracts import thaw
s=create(OUTPUT);s.advance(650);events=[{'time':e['time'],'type':e['type'],'payload':thaw(e['payload'])} for e in s.session.events if e['type'] in ['timeline.finish_requested','timeline.wave_completed'] or e['type']=='timeline.action' and e['payload'].get('wave')==1]
r={'core':CORE,'events':events,'timeline':thaw(s.ctx.state()['timeline']),'source_finish_task_phase':0,'source_expected_offset_seconds':13,'counter_to_fixture_tick641':True};p=ROOT/'validation/campaign/chapter09_stage919_wave_v4/timing.probe.v4.json';assert not p.exists();p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps(events))
