import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m86_immunity_environment_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def fixture():
 p=json.loads((ROOT/'packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json').read_bytes());boss=p['entities'][0];boss['components']['abilities']=['ability/m86/synthetic_stat_probe'];boss['dependencies']=['buff/m70/sleep','buff/m86/chen_source_stun']
 p['entities'].extend([{'id':'unit/m86/chen_cast_fixture','kind':'entity','tags':['player','chen_fixture'],'metadata':{'synthetic_stats':True,'not_canonical_roster':True},'components':{'spatial':{},'attributes':{'base':{'max_hp':10000,'atk':100,'def':0,'mres':0,'attack_interval':1.5,'attack_speed_ratio':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'},'sp':{'initial':0,'capacity':4,'recovery_freeze_abilities':['ability/m86/chen_source_s1']}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/m86/chen_source_s1'],'behavior':{'machine':'behavior/player_combat'}}},{'id':'unit/m86/director','kind':'entity','tags':['player','director'],'components':{'spatial':{},'attributes':{'base':{'max_hp':10000,'atk':25000,'def':0,'mres':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/m86/down','ability/m86/grant','ability/m86/sleep']}}])
 p['selectors'].extend([{'id':'selector/m86/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}],'limit':1},{'id':'selector/m86/chen','kind':'selector','region':{'type':'all'},'filters':[{'tag':'chen_fixture'}],'limit':1},{'id':'selector/m86/director','kind':'selector','region':{'type':'all'},'filters':[{'tag':'director'}],'limit':1}])
 p['abilities'].extend([{'id':'ability/m86/'+name,'kind':'ability','selector':'selector/m86/'+target,'activation':{'mode':'manual','on_start':[effect]},'timeline':[],'metadata':{'synthetic_driver':True}} for name,target,effect in [('down','boss',{'op':'damage','damage_type':'true'}),('grant','chen',{'op':'modify_resource','resource':'sp','amount':4}),('sleep','boss',{'op':'apply_buff','buff':'buff/m70/sleep'}),('synthetic_stat_probe','director',{'op':'damage','damage_type':'true'})]])
 p['scenarioDraft']={'id':'scene/m86/frost_rebirth_immunity','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':5},'initialEntities':[{'definition':boss['id'],'instanceAlias':'boss','position':{'row':1,'col':1}},{'definition':'unit/m86/chen_cast_fixture','instanceAlias':'chen','position':{'row':1,'col':0}},{'definition':'unit/m86/director','instanceAlias':'director','position':{'row':2,'col':4}}]};return p

def make():
 s=Engine.create(Compiler().compile(fixture()),seed=860061)
 for time,source,ability in [(0,'director','grant'),(1,'boss','synthetic_stat_probe'),(17,'director','sleep'),(20,'director','down'),(170,'boss','synthetic_stat_probe'),(173,'director','sleep'),(175,'director','grant'),(240,'director','down')]:s.submit({'action':'skill','source':source,'ability':'ability/m86/'+ability},at=time)
 return s

def test_true_first_health0_clears_sleep_immunity_waits150ticks_restores_same25k630_and_second_sleep_chen_stun():
 s=make();s.advance(19);stun=next(b for b in s.ctx.get('boss',('buffs','instances')) if b['definition']=='buff/m86/chen_source_stun');assert stun['expires_at']-stun['started_at']==45 and stun['applicability']=={'active':True,'control':False};assert s.ctx.buffs.controls('boss')['attack'];boss_ref=s.session.world.resolve('boss')
 s.advance(2);assert s.ctx.resources.current('boss','hp')==0 and s.ctx.alive('boss') and not s.ctx.active('boss') and s.ctx.state()['kills']==0
 assert not any(b['definition']=='buff/ch4/frstar/initial_sleep_immune' for b in s.ctx.get('boss',('buffs','instances')))
 s.advance(150);assert s.session.world.resolve('boss')==boss_ref and s.ctx.resources.current('boss','hp')==25000 and s.ctx.active('boss')
 s.advance(3);assert not s.ctx.buffs.controls('boss')['attack'];s.advance(19);stun=next(b for b in s.ctx.get('boss',('buffs','instances')) if b['definition']=='buff/m86/chen_source_stun');assert stun['applicability']['control'] is False and stun['expires_at']-stun['started_at']==45
 s.advance(49);assert not s.ctx.alive('boss') and s.ctx.state()['kills']==1 and len([e for e in s.session.events if e['type']=='combat.kill'])==1
 packets=[e for e in s.session.events if e['type']=='damage.accepted'];assert [(e['time'],e['payload']['amount']) for e in packets if e['payload']['source']==boss_ref]==[(1,420),(170,630)]
 assert [(e['time'],e['payload']['amount']) for e in packets if e['payload'].get('ability')=='ability/m86/chen_source_s1']==[(16,70),(191,70)]

def test_source_frost_real_down_phase_disk_checkpoint_and_complete_public_replay(tmp_path):
 s=make();s.advance(100);path=tmp_path/'frost_true_down.ordered.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,h));s.advance(142);r.advance(142);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
