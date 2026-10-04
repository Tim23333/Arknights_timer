import json,hashlib
from pathlib import Path
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[]
def test_five_actual_bound_initial_stats_and_birth_motion_cp_replay(tmp_path):
 raw=(ROOT/'packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json').read_bytes();p=json.loads(raw);units=[d for d in p['definitions'] if d['kind']=='entity']
 p['scenarioDraft']={'id':'scene/five/peer','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':25,'cols':20},'initialEntities':[{'definition':u['id'],'instanceAlias':'e'+str(i),'position':{'row':i*5,'col':1},'route':{'motionMode':u['components']['spatial']['motion_mode'],'startPosition':{'row':i*5,'col':1},'endPosition':{'row':i*5,'col':18},'checkpoints':[]}} for i,u in enumerate(units)]}
 actual=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(actual).hexdigest(),'seed':44901,'fixture':json.loads(actual)})
 s=Engine.create(Compiler().compile(json.loads(actual)),seed=44901)
 expected={'enemy_1005_yokai':(800,0,50,0,.9,2.3,20,100,1),'enemy_1005_yokai_2':(1550,220,50,0,.9,3,20,100,1),'enemy_1017_defdrn':(4000,0,150,20,.8,2,20,100,1),'enemy_1013_airdrp':(1450,220,100,0,1,1.9,8,10,0),'enemy_1013_airdrp_2':(2300,300,150,0,1,1.9,8,10,0)}
 for i,u in enumerate(units):
  ident=u['metadata']['native_variant_id'] if 'native_variant_id' in u['metadata'] else u['metadata']['native_variant'];name=ident.split('@')[0];b=s.ctx.get('e'+str(i),('attributes','base'));hp,atk,df,mr,mv,it,rf,ma,mode=expected[name]
  assert tuple(b[k] for k in ['max_hp','atk','def','mres','move_speed','attack_interval'])==(hp,atk,df,mr,mv,it)
  assert s.ctx.resources.current('e'+str(i),'hp')==hp
  spatial=s.ctx.get('e'+str(i),('spatial',));assert spatial['motion_mode']==mode and spatial['steering']['parameters']['response_factor']==rf and spatial['steering']['parameters']['max_acceleration']==ma
 s.advance(44)
 for i,u in enumerate(units):
  col=s.ctx.get('e'+str(i),('spatial','position'))['col'];assert (col==1 if 'airdrp' in u['id'] else col>1)
 pin=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',pin));s.advance(5);r.advance(5)
 for i,u in enumerate(units):assert s.ctx.get('e'+str(i),('spatial','position'))['col']>1
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_native_exact_variant_join_and_no_unused_definitions():
 p=json.loads((ROOT/'packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json').read_bytes());m=p['manifest']['metadata'];rows=m['variant_bindings']
 assert [r['spawn_count'] for r in rows]==[26,8,2,12,4] and len(set(r['unit_definition'] for r in rows))==5
 assert 'buff/chapter02/skulsr_defdown' not in {d['id'] for d in p['definitions']}
 assert all(r['source_block_cost']==1 for r in rows)
 assert [r['source_mass_defined'] for r in rows]==[True,True,False,True,True]
 assert m['stage_executed'] is False and m['client_verified'] is False
