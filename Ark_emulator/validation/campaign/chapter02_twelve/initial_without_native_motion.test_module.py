import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[]
def module():return json.loads((ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.reference_module.json').read_bytes())
def uid(p,name):return next(x['unit_definition'] for x in p['manifest']['metadata']['variant_bindings'] if x['variant_id'].split('@')[0]==name)
def targets(p,positions,block=False):
 u={'id':'unit/fixture/target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'def':100,'mres':25,'block_count':1 if block else 0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 if block:u['components']['deployable']={'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}
 p['definitions'].append(u)
 return [{'definition':u['id'],'instanceAlias':name,'position':{'row':r,'col':c}} for name,r,c in positions]
def scene(p,name,positions,block=False):
 initial=[{'definition':uid(p,name),'instanceAlias':'enemy','position':{'row':3,'col':0},'route':{'motionMode':0,'startPosition':{'row':3,'col':0},'endPosition':{'row':3,'col':8},'checkpoints':[]}}]+targets(p,positions,block)
 p['scenarioDraft']={'id':'scene/twelve/'+name,'ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':8,'cols':10},'initialEntities':initial};return p
def create(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':48107,'fixture':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=48107)
def exact(s,tmp_path):
 receipt=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',receipt));s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
@pytest.mark.parametrize('name,frame,damage',[('enemy_1027_mob',12,150),('enemy_1027_mob_2',12,250),('enemy_1002_nsabr',12,100),('enemy_1015_litamr',13,150),('enemy_1030_wteeth',19,400),('enemy_1033_handax',28,650),('enemy_1006_shield',14,500)])
def test_seven_real_melee_first_frame_and_table_settlement(name,frame,damage,tmp_path):
 s=create(scene(module(),name,[('blocker',3,0)],True));s.advance(frame+2)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [(e['time'],e['payload']['amount']) for e in hits]==[(frame+1,damage)]
 assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('blocker');exact(s,tmp_path)
@pytest.mark.parametrize('name,impact,damage',[('enemy_1011_wizard',22,150),('enemy_1028_mocock',28,80)])
def test_real_ranged_projectile_source_clock_arts_or_physical(name,impact,damage,tmp_path):
 s=create(scene(module(),name,[('target',3,1)]));s.advance(29)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [(e['time'],e['payload']['amount']) for e in hits]==[(impact,damage)];exact(s,tmp_path)
def test_aoemag_actual_predelay21_cross5_not_diagonal_or_spine24(tmp_path):
 p=scene(module(),'enemy_1018_aoemag',[('main',3,1),('down',4,1),('right',3,2),('diagonal',4,2)])
 # Two target definitions isolate source selectors from area splash eligibility.
 fly=deepcopy(p['definitions'][-1]);fly['id']='unit/fixture/fly';fly['components']['selection_state']['motion']=2;p['definitions'].append(fly);p['scenarioDraft']['initialEntities'][2]['definition']=fly['id']
 s=create(p);s.advance(22);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[21,21,21]
 assert [e['payload']['amount'] for e in hits]==[180,180,180]
 assert s.ctx.resources.current('diagonal','hp')==10000;exact(s,tmp_path)
def test_aoemag_reference_radius2_15_accepted_source_point_profile_rejected(tmp_path):
 p=scene(module(),'enemy_1018_aoemag',[('target',3,2.15)]);s=create(p);s.advance(22);assert s.ctx.resources.current('target','hp')==9820;exact(s,tmp_path)
 p=scene(module(),'enemy_1018_aoemag',[('target',3,2.15)]);selector=next(d for d in p['definitions'] if d['kind']=='selector' and 'enemy_1018_aoemag' in d['id']);selector['region']['radius']=2.0999999046325684
 # Freeze movement for22 ticks so distance policy comparison has identical origins.
 p['buffs']=[{'id':'buff/fixture/still','kind':'buff','duration_seconds':1,'control':{'move':False}}];p['scenarioDraft']['initialEntities'][0]['components']={'buffs':{'initial':['buff/fixture/still']}}
 s=create(p);s.advance(22);assert s.ctx.resources.current('target','hp')==10000 and not any(e['type']=='ability.started' for e in s.session.events);exact(s,tmp_path)
def test_exact_twelve_stats_and_typed_field_inputs_no_regen_fabrication(tmp_path):
 p=module();rows=p['manifest']['metadata']['variant_bindings'];expected=[1700,1550,2650,1650,2500,1600,7000,5000,8000,6000,10500,4000]
 p['scenarioDraft']={'id':'scene/twelve/stats','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':36,'cols':12},'initialEntities':[{'definition':r['unit_definition'],'instanceAlias':'e'+str(i),'position':{'row':i*3,'col':0},'route':{'motionMode':1 if i==11 else 0,'startPosition':{'row':i*3,'col':0},'endPosition':{'row':i*3,'col':10},'checkpoints':[]}} for i,r in enumerate(rows)]}
 s=create(p)
 for i,hp in enumerate(expected):
  assert s.ctx.resources.current('e'+str(i),'hp')==hp
  assert s.ctx.get('e'+str(i),('selection_state','motion'))==(2 if i==11 else 1)
 assert sum(r['spawn_count'] for r in rows)==36
 s.advance(5)
 for i in range(12):assert s.ctx.get('e'+str(i),('spatial','position'))['col']>0
 exact(s,tmp_path)

@pytest.mark.parametrize('name,impact,damage',[('enemy_1011_wizard',21,150),('enemy_1028_mocock',24,80)])
def test_source_bound_combat_input_target_blocker_beats_nearer_taunt(name,impact,damage,tmp_path):
 p=scene(module(),name,[('blocker',3,0),('other',3,1)],True)
 # Keep normal disabled through initial block reconciliation; declared fixture, not source skill rewrite.
 p['buffs']=[{'id':'buff/fixture/preblock','kind':'buff','duration_seconds':1/30,'control':{'attack':False}}];p['scenarioDraft']['initialEntities'][0]['components']={'buffs':{'initial':['buff/fixture/preblock']}}
 other=deepcopy(p['definitions'][-1]);other['id']='unit/fixture/taunt';other['components']['attributes']['base']['taunt_level']=10;other['components']['attributes']['base']['block_count']=0;other['components'].pop('deployable');p['definitions'].append(other);p['scenarioDraft']['initialEntities'][-1]['definition']=other['id']
 s=create(p);s.advance(31);hits=[e for e in s.session.events if e['type']=='damage.accepted']
 # Source and blocker share a cell, so no positive flight distance: first motion update is one tick after signal.
 assert [(e['time'],e['payload']['target'],e['payload']['amount']) for e in hits]==[(impact,s.session.world.resolve('blocker'),damage)]
 assert s.ctx.resources.current('other','hp')==10000;exact(s,tmp_path)

def test_aoemag_atk_buff_res_and_every_cross_cell_once_excludes_enemy(tmp_path):
 p=scene(module(),'enemy_1018_aoemag',[('main',3,1),('up',2,1),('down',4,1),('left',3,0),('right',3,2),('diagonal',4,2)])
 p['buffs']=[{'id':'buff/fixture/atk2','kind':'buff','modifiers':[{'attribute':'atk','layer':'direct_ratio','value':1}]}];p['scenarioDraft']['initialEntities'][0]['components']={'buffs':{'initial':['buff/fixture/atk2']}}
 # Disable primary eligibility for surrounding probes, preserving area membership.
 fly=deepcopy(p['definitions'][-1]);fly['id']='unit/fixture/splash';fly['components']['selection_state']['motion']=2;p['definitions'].append(fly)
 for x in p['scenarioDraft']['initialEntities'][2:]:x['definition']=fly['id']
 enemy=deepcopy(fly);enemy['id']='unit/fixture/nonplayer';enemy['tags']=['enemy'];enemy['components']['selection_state']['side']=1;p['definitions'].append(enemy);p['scenarioDraft']['initialEntities'].append({'definition':enemy['id'],'instanceAlias':'foreign','position':{'row':3,'col':2}})
 s=create(p);s.advance(22);hits=[e for e in s.session.events if e['type']=='damage.accepted']
 assert len(hits)==5 and [e['time'] for e in hits]==[21]*5 and [e['payload']['amount'] for e in hits]==[360]*5
 assert {e['payload']['target'] for e in hits}=={s.session.world.resolve(x) for x in ['main','up','down','left','right']}
 assert s.ctx.resources.current('foreign','hp')==10000 and s.ctx.resources.current('diagonal','hp')==10000;exact(s,tmp_path)
