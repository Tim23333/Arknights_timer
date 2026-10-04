import sys,json
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m70_buff_applicability_v2_candidate'));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def fixture():
 p=json.loads((ROOT/'packages/campaign/chapter04_boss/m70/immunity.reference_model.json').read_bytes());boss=p['entities'][0]
 boss['dependencies']=['buff/campaign_chen_stun','buff/m70/sleep'];p['entities'].append({'id':'unit/director','kind':'entity','tags':['player'],'components':{'spatial':{},'abilities':['ability/chen_source_stun','ability/sleep','ability/phase2']}})
 p['selectors']=[{'id':'selector/frost','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}],'limit':1}]
 p['abilities']=[{'id':'ability/'+name,'kind':'ability','selector':'selector/frost','activation':{'mode':'manual','on_start':[effect]},'timeline':[],'metadata':{'synthetic_driver_only':True}} for name,effect in [('chen_source_stun',{'op':'apply_buff','buff':'buff/campaign_chen_stun'}),('sleep',{'op':'apply_buff','buff':'buff/m70/sleep'}),('phase2',{'op':'remove_buff','buff':'buff/ch4/frstar/initial_sleep_immune'})]]
 p['scenarioDraft']={'id':'scene/frost/immunity/phase_probe','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':4},'initialEntities':[{'definition':boss['id'],'instanceAlias':'boss','position':{'row':1,'col':1}},{'definition':'unit/director','instanceAlias':'director','position':{'row':2,'col':3}}]};return p

def test_frost_exact_intrinsic_immunity_chen_source_stun_and_sleep_phase_public_disk_replay(tmp_path):
 p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=700061)
 for time,ability in [(1,'chen_source_stun'),(3,'sleep'),(6,'phase2')]:s.submit({'action':'skill','source':'director','ability':'ability/'+ability},at=time)
 s.advance(5);assert s.ctx.buffs.controls('boss')=={'move':True,'attack':True,'abilities':True,'block':True};assert s.ctx.resources.current('boss','hp')==25000
 path=tmp_path/'frost_immunity.ordered.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(3);r.advance(3)
 assert s.ctx.buffs.controls('boss')=={'move':False,'attack':False,'abilities':False,'block':False}
 from ark_sim.domains.selection import DEFAULT_STATE
 status=s.ctx.spatial.selection_state('boss',DEFAULT_STATE);assert status['abnormal_immunes']==[0,12,16,25] and status['abnormal_combos']==[0] and status.get('abnormal_combo_immunes',[])==[]
 assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()

def test_exact_raw_and_phase_only_scope_not_false_native_rebirth():
 p=fixture();m=p['manifest']['metadata'];assert m['source_chen_stun_buff']['attributes']['abnormalFlags']==[0] and m['source_initial_sleep_buff']['attributes']['abnormalComboImmunes']==[0]
 assert m['client_verified'] is False and 'rebirth' not in p['entities'][0]['components'] and any('rebirth' in x for x in m['model_gaps'])
