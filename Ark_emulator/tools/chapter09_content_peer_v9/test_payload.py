from tools.chapter09_content_peer_v9.fixture import *
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest,json

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=91917777)
def events(s,kind):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==kind]
def proof(p,name,split,end):
 a=create(p);a.advance(split);LOG.mkdir(parents=True,exist_ok=True);path=LOG/(name+'.checkpoint.json');pin=write_ordered(path,a.checkpoint());b=Engine.restore(a.program,load_bound(path,pin),providers=REG);a.advance(end-split);b.advance(end-split);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending
 REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'runtime':CORE,'CP_head_full_equal':True,'input_digest':digest(p),'CP_SHA':pin,'events':len(a.session.events),'whole_stage':False},indent=2),encoding='utf8');return a
@pytest.mark.parametrize('direction',['up','left','down','right'])
def test_actual_source_payload_new_positions_true_damage_and_owned_ruins(direction):
 p=pillar_scene(direction);s=proof(p,'pillar_'+direction,44,48);assert not events(s,'command.rejected');assert s.ctx.resources.current('ground','hp')==s.ctx.resources.current('flying','hp')==5777;assert s.ctx.resources.current('off_axis','hp')==17777;assert not s.ctx.alive('player');assert s.ctx.resources.current('player','hp')==17777;assert not s.ctx.alive('pillar')
 assert [x['amount'] for _,x in events(s,'damage.accepted')]==[12000,12000]
 for alias in ['ground','flying']:
  stun=[b for b in s.ctx.get(alias,('buffs','instances')) if b['definition']=='buff/ch9/pillar/stun10'];assert len(stun)==1;assert stun[0]['started_at']==45 and stun[0]['expires_at']==345
 tokens=events(s,'tile.token_created');assert len(tokens)==2
 for t,x in tokens:
  assert t==45;token=x['token'];assert s.ctx.resources.current(token,'hp')==100;assert s.ctx.attributes.value(token,'block_count')==3;assert s.ctx.get(token,('ownership','owner'))==s.session.world.resolve('pillar');assert s.ctx.alive(token);cell=x['cell'];tile=s.ctx.spatial.grid.tile(cell['row'],cell['col']);assert tile['buildableType']==0 and tile['passableMask']==1
@pytest.mark.parametrize('mode',['free','invisible','camo'])
def test_pillar_typed_qualifications_do_not_hit_excluded_enemy(mode):
 s=proof(pillar_scene(mode=mode),'qualification_'+mode,44,48);assert s.ctx.resources.current('ground','hp')==17777;assert s.ctx.resources.current('flying','hp')==5777

def test_pillar_uses_late_actual_occupant_and_wall_does_not_spawn():
 s=proof(pillar_scene(mode='late'),'late_occupant',43,48);assert not events(s,'command.rejected');assert s.ctx.resources.current('ground','hp')==5777
 s=proof(pillar_scene(mode='wall'),'wall_no_spawn',44,48);assert len(events(s,'tile.token_created'))==1;assert s.ctx.spatial.grid.tile(3,5)['buildableType']==0;assert s.ctx.spatial.grid.tile(3,5)['passableMask']==0

def test_body_death_retains_tokens_but_token_death_removes_only_its_terrain():
 s=create(pillar_scene());s.advance(48);tokens=[x['token'] for _,x in events(s,'tile.token_created')];assert not s.ctx.alive('pillar');assert all(s.ctx.alive(t) for t in tokens)
 first=s.ctx.get(tokens[0],('spatial','position'));s.ctx.resources.adjust(tokens[0],'hp',value=0);assert not s.ctx.alive(tokens[0]);assert s.ctx.spatial.grid.tile(first['row'],first['col'])['buildableType']==1;assert s.ctx.alive(tokens[1]);second=s.ctx.get(tokens[1],('spatial','position'));assert s.ctx.spatial.grid.tile(second['row'],second['col'])['buildableType']==0

def test_actual_pillar_body_trait_skips_real_gargoyle_first_death():
 p=gargoyle_scene();p['scenarioDraft']['commands']=[{'at':0,'action':'skill','source':'pillar','ability':'ability/ch9/pillar/collapse_right'}];s=proof(p,'pillar_garg_actual',44,48);assert not s.ctx.alive('garg');assert s.ctx.resources.current('garg','mode')==3;assert len(events(s,'entity.rebirth.skipped'))==1;assert not events(s,'entity.rebirth.started')
@pytest.mark.parametrize('origin',['noBuff','targetOnly','nonDamage'])
def test_gargoyle_requires_actual_damage_source_trait_not_names_or_target_marker(origin):
 p=gargoyle_scene()
 if origin=='targetOnly':next(e for e in p['entities'] if '/dugago/' in e['id'])['components']['buffs']['initial'].append('buff/ch9/pillar/trait')
 if origin=='nonDamage':next(e for e in p['entities'] if e['id']=='unit/peer/controller')['components']['buffs']={'initial':['buff/ch9/pillar/trait']}
 p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'controller','ability':'ability/peer/'+('sethp' if origin=='nonDamage' else 'kill')}];s=proof(p,'garg_'+origin,1,4);assert s.ctx.alive('garg');assert s.ctx.resources.current('garg','mode')==1;assert s.ctx.resources.current('garg','hp')==pytest.approx(2000.0000298023224);assert not events(s,'entity.rebirth.skipped')

def test_gargoyle_second_death_cannot_rebirth_and_pre_zero_rule_error_is_atomic():
 p=gargoyle_scene();p['scenarioDraft']['commands']=[{'at':t,'action':'skill','source':'controller','ability':'ability/peer/kill'} for t in [2,4]];s=proof(p,'garg_second_death',3,6);assert not s.ctx.alive('garg');assert len(events(s,'entity.rebirth.started'))==1
 p=gargoyle_scene();reg=dict(REG);reg['reference.ch9.source_buff_skip']={'callable':lambda i,p,c:1,'version':'peer_invalid_boolean'};program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);s.advance(1);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('controller',['garg'],{'op':'damage','damage_type':'true','scale':1})
 assert s.checkpoint()==before

def test_source_and_frozen_helper_guard():assert guard()==START
