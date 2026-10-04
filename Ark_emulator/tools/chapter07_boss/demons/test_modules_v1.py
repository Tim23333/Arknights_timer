"""Public mode transitions and exact three demon source mechanisms."""
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter07_boss.demons.build_modules import OUT,NAMES,LISTENER,IMMUNE
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def package(name,*,outer=False):
 p=json.loads((OUT/(name+'.module.v1.json')).read_bytes());uid=p['entities'][0]['id'];mode1='ability/test/demon/mode1';mode0='ability/test/demon/mode0'
 p['entities'].append({'id':'unit/test/demon/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':1000000,'atk':0,'def':100,'mres':25,'block_count':3}},'resources':{'hp':{'initial':1000000,'capacity':1000000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
 p['entities'].append({'id':'unit/test/demon/controller','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'abilities':[mode0,mode1]}})
 p['selectors'].append({'id':'selector/test/demon/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'ore_responsive'},{'state':'alive'}],'limit':1})
 for mode,aid in [(0,mode0),(1,mode1)]:p['abilities'].append({'id':aid,'kind':'ability','selector':'selector/test/demon/enemy','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'transition','state':'mode'+str(mode)}}]})
 scene={'id':'scene/ch7/demons/'+name,'ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':7},'resources':{'dp':{'initial':20,'capacity':99},'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':uid,'instanceAlias':'enemy','position':{'row':2,'col':2},'route':{'motionMode':'WALK','startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':5},'checkpoints':[]}},{'definition':'unit/test/demon/controller','instanceAlias':'controller','position':{'row':4,'col':6}}],'roster':['unit/test/demon/player']}
 if outer:
  # Keep center static onlyfor radius probe; notnative movement policy.
  scene['initialEntities'][0].pop('route');p['manifest']['metadata']['radius_probe_static_center']=True
 scene['initialEntities'] += [{'definition':'unit/test/demon/player','instanceAlias':'a','position':{'row':2,'col':3}},{'definition':'unit/test/demon/player','instanceAlias':'b','position':{'row':3,'col':2}}] if name!='enemy_1084_sotidm' else []
 if outer:scene['initialEntities'].append({'definition':'unit/test/demon/player','instanceAlias':'outer','position':{'row':2,'col':4}})
 p['scenarioDraft']=scene;return p
def make(name,**kw):return Engine.create(Compiler().compile(package(name,**kw)),seed=7178)
def deploy(s):s.submit({'action':'deploy','definition':'unit/test/demon/player','alias':'player','position':{'row':2,'col':2}},at=0)
def change(s,mode,tick):s.submit({'action':'skill','source':'controller','ability':'ability/test/demon/mode'+str(mode)},at=tick)
def ev(s,name):return [e for e in s.session.events if e['type']==name]
def packets(s):return [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('enemy')]
def test_source_melee_physical16_then_hooked_magic29_preserves_realclock():
 s=make(NAMES[0]);deploy(s);s.session.advance(17);assert packets(s)==[(16,380)];change(s,1,40);s.session.advance(110-17)
 assert packets(s)==[(16,380),(104,360)]
 assert s.ctx.get('enemy',('behavior','state'))=='mode1' and not any(b['definition']==LISTENER for b in s.ctx.get('enemy',('buffs','instances'),[]))
 assert any(b['definition']==IMMUNE for b in s.ctx.get('enemy',('buffs','instances'),[]))
def test_public_midwindup_fsm_restart_cancels_old_physical_not_newfake_attack():
 s=make(NAMES[0]);deploy(s);change(s,1,5);s.session.advance(110)
 assert packets(s)==[(104,360)] and ev(s,'ability.interrupted')
@pytest.mark.parametrize('name',NAMES[1:])
def test_actual_caster_nevertrigger_init0_then_5seconds_immo_once_area(name):
 s=make(name,outer=True);s.session.advance(151);atk=350 if name==NAMES[1] else 450
 assert packets(s)==[(0,atk*.75),(0,atk*.75),(150,atk*.75),(150,atk*.75)]
 assert len(ev(s,'area.resolved'))==2 and all('/immo0' in e['payload']['ability'] for e in ev(s,'ability.started'))
 assert s.ctx.attributes.value('enemy','attack_interval')==pytest.approx(5-4.900000095367432)
@pytest.mark.parametrize('name',NAMES[1:])
def test_public_caster_enhanced_radius25_immediate_skillclock_not_point1(name):
 s=make(name,outer=True);change(s,1,2);s.session.advance(153);atk=350 if name==NAMES[1] else 450
 assert packets(s)==[(0,atk*.75),(0,atk*.75),(2,atk*.75),(2,atk*.75),(2,atk*.75),(152,atk*.75),(152,atk*.75),(152,atk*.75)]
 assert len(ev(s,'area.resolved'))==3 and not any('/normal' in e['payload']['ability'] for e in ev(s,'ability.started'))
@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('tick',[3,15])
def test_public_mode_cp_head_sameactor_source_profile(name,tick,tmp_path):
 s=make(name,outer=name!=NAMES[0])
 if name==NAMES[0]:deploy(s)
 change(s,1,2 if name!=NAMES[0] else 5);s.session.advance(tick);p=tmp_path/'demon.json';h=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,h));s.session.advance(160-tick);r.session.advance(160-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
