import sys,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
def fixture(short=False):
 p=json.loads((ROOT/'packages/campaign/chapter03_models/mortar.primary.reference.json').read_bytes());old=json.loads((ROOT/'validation/campaign/chapter03_mortar/moving_live/input.json').read_bytes())
 for name in ('entities','abilities','selectors','buffs','rules'):
  ids={row['id'] for row in p.get(name,[])};p.setdefault(name,[]).extend(row for row in old.get(name,[]) if row['id'] not in ids)
 p['scenarioDraft']=old['scenarioDraft']
 if short:p['projectiles'][0]['lifetime_seconds']=.1
 return p
def make(p):return Engine.create(Compiler().compile(p),seed=5916)
def test_actual_new_mortar_f16_and_moving_at_hit_are_unchanged():
 s=make(fixture());s.submit({'action':'skill','source':'main','ability':'ability/move'},at=30);s.submit({'action':'skill','source':'director','ability':'ability/boost'},at=30);s.advance(65)
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(54,450),(54,450)]
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_stress_short_expiry_forced_legal_primary_has_packet350_outside_local_grid():
 s=make(fixture(True));s.advance(50)
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(19,350)]
 assert s.ctx.resources.current('main','hp')==4650 and s.ctx.resources.current('neighbor','hp')==5000
@pytest.mark.parametrize('mode',['dead','free'])
def test_forced_expiry_captured_primary_never_bypasses_liveness_or_targetfree(mode):
 p=fixture(True)
 if mode=='dead':ability='ability/withdraw'
 else:
  p['buffs'].append({'id':'buff/expiryfree','kind':'buff','selection_flags':{'target_free':True}});p['abilities'].append({'id':'ability/expiryfree','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/expiryfree'}]},'timeline':[]});next(e for e in p['entities'] if e['id']=='unit/target')['components']['abilities'].append('ability/expiryfree');ability='ability/expiryfree'
 s=make(p);s.submit({'action':'skill','source':'main','ability':ability},at=18);s.advance(25);assert not [e for e in s.session.events if e['type']=='damage.accepted']
