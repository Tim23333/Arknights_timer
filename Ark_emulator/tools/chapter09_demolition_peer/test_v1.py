from tools.chapter09_demolition_peer.fixture import *
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=28361811)
def events(s,t):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==t]
def proof(p,name,split=43,end=100):
 a=create(p);a.advance(split);LOG.mkdir(parents=True,exist_ok=True);path=LOG/(name+'.checkpoint.json');pin=write_ordered(path,a.checkpoint());b=Engine.restore(a.program,load_bound(path,pin),providers=REG);a.advance(end-split);b.advance(end-split);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'core':CORE,'actual_CPP_head_full_equal':True,'CP_SHA':pin,'input_digest':digest(p),'events':len(a.session.events)},indent=2),encoding='utf8');return a

def test_four_directions_passive35_ticks_true2000_stock_DP_slotzero():
 for d in ['up','down','left','right']:
  p=scene(d);s=create(p);s.advance(42);assert s.ctx.resources.current('enemy','hp')==HP;s.advance(1);assert s.ctx.resources.current('enemy','hp')==HP-2000;assert not s.ctx.alive('device');assert [t for t,_ in events(s,'damage.accepted')]==[42]
  s=proof(p,'native_'+d);assert s.ctx.resources.current('system/battle','dp')==32;assert s.ctx.resources.current('system/battle',STOCK)==1;assert s.ctx.state()['deployments'][BODY]['ready_at']==157

def test_live_masks_camo_invisibility_ground_free_and_hit_time_leave():
 p=scene();variants=[('fly',{'motion':2}),('friend',{'side':0}),('trap',{'category':2}),('free',{'free':True}),('hidden',{'flags':(9,)}),('camo',{'camo':True}),('profession',{'profession':512})]
 for n,kw in variants:
  a=actor(n,**kw);p['entities'].append(a);p['scenarioDraft']['initialEntities'].append({'definition':a['id'],'instanceAlias':n,'position':{'row':3,'col':4}})
 s=proof(p,'masks');assert [s.ctx.resources.current(n,'hp') for n,_ in variants]==[HP,HP,HP,HP-2000,HP,HP,HP-2000]
 p=scene();p['abilities'].append({'id':'ability/peer/leave','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':{'row':6,'col':7}}}]});p['entities'][1]['components']['abilities']=['ability/peer/leave'];p['scenarioDraft']['commands'].append({'at':41,'action':'skill','source':'enemy','ability':'ability/peer/leave'});s=proof(p,'hit_time');assert s.ctx.resources.current('enemy','hp')==HP

def test_force_plus_actual_source_bonus_minus_mass_and_immovable():
 p=scene(mass=3);p['entities'][0]['components']['attributes']['base']['base_force_level']=3;s=proof(p,'push_bonus',end=130);assert abs(s.ctx.get('enemy',('spatial','position'))['col']-(4+1.98705))<1e-9
 p=scene(mass=0);p['entities'][1]['components']['selection_state']['abnormal_flags']=[8];s=proof(p,'immovable',end=130);assert s.ctx.get('enemy',('spatial','position'))=={'row':3,'col':4};assert s.ctx.resources.current('enemy','hp')==HP-2000

def test_actual_four_deploy_attempts_two_stock_five_seconds_and_zero_refund():
 p=scene();p['scenarioDraft']['commands']=[{'at':t,'action':'deploy','definition':BODY,'alias':'dev'+str(t),'position':{'row':3,'col':3},'facing':'right'} for t in [7,156,157,307]];s=proof(p,'four_deploy',split=110,end=350);assert [t for t,_ in events(s,'command.accepted')]==[7,157];assert [t for t,_ in events(s,'command.rejected')]==[156,307];assert s.ctx.resources.current('system/battle','dp')==27;assert s.ctx.resources.current('system/battle',STOCK)==0
 p=scene();p['scenarioDraft']['commands'].append({'at':31,'action':'withdraw','source':'device'});s=proof(p,'withdraw');assert not events(s,'damage.accepted');assert s.ctx.resources.current('system/battle','dp')==32;assert s.ctx.resources.current('enemy','hp')==HP

def test_supplied_pillar_direct_all_directions_keeps_HP5000_pays_SP10():
 for d in ['up','down','left','right']:
  p=scene(d,pillar=True);s=create(p);s.advance(43);assert s.ctx.resources.current('pillar','hp')==5000;assert s.ctx.resources.current('pillar','sp')==0;assert [(t,x['ability']) for t,x in events(s,'ability.started') if x['ability'].startswith('ability/ch9/pillar/collapse_')]==[(42,'ability/ch9/pillar/collapse_'+d)]
  s=proof(p,'direct_pillar_'+d);assert s.ctx.resources.current('pillar','hp')==5000;assert not s.ctx.alive('pillar');assert len(events(s,'tile.token_created'))==2

def test_terrain_build_masks_real_card_rejects_no_stock_DP_loss():
 for tile,name in [({'tileKey':'tile_wall','passableMask':0,'buildableType':2,'advancedBuildMask':1},'wall'),({'tileKey':'tile_road','passableMask':1,'buildableType':0,'advancedBuildMask':1},'no_build'),({'tileKey':'tile_floor','passableMask':1,'buildableType':1,'advancedBuildMask':2},'wrong_mask')]:
  p=scene();tiles=[{'tileKey':'tile_floor','passableMask':1,'buildableType':1} for _ in range(80)];tiles[33]=tile;p['scenarioDraft']['map']['tiles']=tiles;s=proof(p,'terrain_'+name)
  if name=='wall':assert events(s,'command.accepted') and s.ctx.resources.current('system/battle','dp')==32
  else:assert events(s,'command.rejected');assert s.ctx.resources.current('system/battle','dp')==37;assert s.ctx.resources.current('system/battle',STOCK)==2

def test_actual_current_source_guard_and_missing_dependency_reject():
 assert guard()==START
 p=build(pillar_abilities={d:'ability/peer/missing_'+d for d in ['up','down','left','right']});p['scenarioDraft']=scene()['scenarioDraft']
 with pytest.raises(ValueError):Compiler(providers=REG).compile(p)


def test_actual_environment_hook_ordinary_damage_and_stage_one_stock():
 p=scene();p['entities'][1]['components']['attributes']['base']['atk']=19;p['entities'][1]['components']['abilities']=['ability/peer/ordinary'];p['selectors']=[{'id':'selector/peer/device','kind':'selector','region':{'type':'all'},'filters':[{'tag':'demolition'}]}];p['abilities'].append({'id':'ability/peer/ordinary','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/device','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]});p['rules'].append({'id':'rule/peer/environment','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'amount','expression':"{'accepted': True, 'amount': inputs.effect.fixed_amount, 'allocations': [], 'events': []}"}],'output':'nodes.amount'}});p['scenarioDraft']['scheduledEffects']=[{'at':11,'effect':{'op':'no_source_damage','target':3,'damage_type':'true','fixed_amount':19,'attack_type':'NONE','damage_without_modify':False,'ignore_for_sp':True,'node_is_env_damage':True,'env_blackboard_injected':False,'environmental':True,'origin':{'kind':'reference_environment'},'rules':{'damage.pipeline':'rule/peer/environment'}}}];p['scenarioDraft']['commands'].append({'at':13,'action':'skill','source':'enemy','ability':'ability/peer/ordinary'});preview=create(p);preview.advance(8);assert preview.session.world.resolve('device')==3;s=proof(p,'actual_environment',split=14,end=30);assert s.ctx.resources.current('device','hp')==81;assert [(t,x['amount']) for t,x in events(s,'damage.accepted')]==[(11,0),(13,19)]
 q=build('level_main_09-17');assert q['manifest']['metadata']['native_card']['initialCnt']==1;q['scenarioDraft']=scene()['scenarioDraft'];q['scenarioDraft']['initialEntities']=[];q['scenarioDraft']['resources'][STOCK]={'initial':1,'capacity':1};q['scenarioDraft']['commands']=[{'at':t,'action':'deploy','definition':BODY,'alias':'single'+str(t),'position':{'row':3,'col':3},'facing':'up'} for t in [7,157]];s=proof(q,'stage_stock_one',split=80,end=200);assert [t for t,_ in events(s,'command.accepted')]==[7];assert [t for t,_ in events(s,'command.rejected')]==[157];assert s.ctx.resources.current('system/battle',STOCK)==0;assert s.ctx.resources.current('system/battle','dp')==32
