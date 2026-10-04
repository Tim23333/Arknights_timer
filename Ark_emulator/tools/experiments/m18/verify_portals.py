"""Bounded coherent candidate/source witnesses; never a receipt."""
import hashlib
import json
import difflib
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];CANDIDATE=ROOT.parent/'unpack_work/campaign_m18_portal_candidate';BASE=ROOT.parent/'unpack_work/campaign_m16_terrain_candidate'
sys.path.insert(0,str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==CANDIDATE/'ark_sim'
sys.path.append(str(ROOT))
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from tools.experiments.m18 import test_portals as t
from tools.experiments.m15_peer import verify as h
from tools.build_chapter01_portal_model import build,OUTPUT,AUDIT,EMP,BASE as STAGE
import pytest
OUT=ROOT/'validation/campaign/m18_portal';OUT.mkdir(parents=True,exist_ok=True)
COPIED=ROOT/'tools/experiments/m18/test_terrain_compat.py';ORIGINAL=ROOT/'tools/experiments/m16/test_terrain.py'
assert COPIED.read_text()==ORIGINAL.read_text().replace('campaign_m16_terrain_candidate','campaign_m18_portal_candidate')
assert build()==json.loads(OUTPUT.read_bytes())
files=[Path(__file__),Path(t.__file__),COPIED,ORIGINAL,Path(h.__file__),ROOT/'tools/build_chapter01_portal_model.py',
 OUTPUT,AUDIT,EMP,STAGE,CANDIDATE/'ark_sim/rules/contracts.json',CANDIDATE/'ark_sim/content/presets/ark_standard.json']
source=json.loads(AUDIT.read_bytes());files.append(ROOT.parent/source['tile_asset']['path'])
files.extend(ROOT.parent/x['source']['path'] for x in source['script_sources'].values())
def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
start=hashes();core=implementation_digest();cases=[]
class Capture:
    old=None
    def pytest_runtest_setup(self,item):self.old=(t.LAST,h.LAST)
    def pytest_runtest_makereport(self,item,call):
        if call.when!='call':return
        c={'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'}
        if call.excinfo is not None:c['error']=str(call.excinfo.value)
        s=t.LAST if t.LAST is not self.old[0] else h.LAST if h.LAST is not self.old[1] else None
        if s is not None:
            c['fixture']={'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'initial_scenario':thaw(s.program.scenario),
              'commands':s.export_replay(),'world':s.snapshot(),'events':[thaw(e) for e in s.session.events if e['type'].startswith(('movement.','terrain.','command.','entity.','ability.'))],
              'all_events_sha256':digest([thaw(e) for e in s.session.events])}
        cases.append(c)
code=pytest.main(['-q',str(Path(t.__file__)),str(COPIED)],plugins=[Capture()]);end=hashes();stable=start==end and implementation_digest()==core
old=json.loads((OUT/'legacy_m16.json').read_bytes());new=json.loads((OUT/'legacy_m18.json').read_bytes())
equal=old['event_count']==new['event_count'] and old['normalized_event_sha256']==new['normalized_event_sha256'] and new['implementation']==core
passed=code==0 and stable and equal
report={'schema':'ark-sim/route-tile-profile-candidate-evidence/v1','passed':passed,'formal_approval':False,'review_receipt':False,
 'implementation_sha256':core,'runtime_module':ark_sim.__file__,'source_at_start':start,'source_at_completion':end,'identity_stable':stable,
 'cases':cases,'legacy_no_profile':{'passed':equal,'old_core':old['implementation'],'new_core':core,'event_count':old['event_count'],
   'normalized_event_sha256':old['normalized_event_sha256'],'excluded_identity_field_names':old['ignored_fields']},
 'source_scope':'Explicit source-preserving tile profiles and actual 3/35/40s route excerpts; no full native route/stage/client approval',
 'tests':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'source_sha256':start[str(p)],'result':'passed' if code==0 else 'failed'} for p in (Path(t.__file__),COPIED)]}
(OUT/'candidate_final.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
changed=[];patch=[]
for p in sorted((CANDIDATE/'ark_sim').rglob('*')):
 if not p.is_file() or p.suffix not in ('.py','.json'):continue
 rel=p.relative_to(CANDIDATE);oldpath=BASE/rel
 if oldpath.exists() and oldpath.read_bytes()==p.read_bytes():continue
 changed.append({'path':str(rel).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 patch.extend(difflib.unified_diff(oldpath.read_text().splitlines(True) if oldpath.exists() else [],p.read_text().splitlines(True),
  fromfile='a/'+str(rel).replace('\\','/'),tofile='b/'+str(rel).replace('\\','/')))
(OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8',newline='')
(OUT/'changed_files.json').write_text(json.dumps({'core':core,'files':changed},indent=2)+'\n',encoding='utf8')
print(json.dumps({'passed':passed,'core':core,'cases':len(cases),'portal_tests':sum('test_portals.py' in x['nodeid'] for x in cases),
 'package':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),'legacy':equal}))
raise SystemExit(0 if passed else 1)
