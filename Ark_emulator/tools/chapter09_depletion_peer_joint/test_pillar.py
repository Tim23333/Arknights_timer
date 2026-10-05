"""Independent full pillar true-healthzero source chain on fixed candidate."""
from tools.chapter09_depletion_peer_joint.pillar_fixture import *
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=24689863)
def events(s,kind):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==kind]
def proof(p,name,splits,end):
 a=create(p);a.advance(end);b=create(p);pins=[];LOG.mkdir(exist_ok=True)
 for i,t in enumerate(splits):
  b.advance(t-b.session.time);path=LOG/(name+str(i)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append(pin);b=Engine.restore(b.program,load_bound(path,pin),providers=REG)
 b.advance(end-b.session.time);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();REPORT.mkdir(exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'core':CORE,'actual_full_pillar_CPP_head_equal':True,'input_digest':digest(p),'CP_SHAs':pins,'events':len(a.session.events)},indent=2),encoding='utf8');return a
@pytest.mark.parametrize('direction',['up','down','left','right'])
def test_two_actual_hits_zero_HP_two_seconds_ready_owned45_cast_payload(direction):
 p=scene(direction);s=create(p);s.advance(14);assert s.ctx.resources.current('pillar','hp')==0 and s.ctx.alive('pillar');assert s.ctx.depletion.state(s.session.world.resolve('pillar'))['stage']=='damaged';s.advance(60);assert s.ctx.depletion.state(s.session.world.resolve('pillar'))['stage']=='ready';assert s.ctx.resources.current('pillar','hp')==0
 s=proof(p,'fullpillar_'+direction,[14,74,90],131);assert not events(s,'command.rejected');assert not s.ctx.alive('pillar');assert s.ctx.resources.current('ground','hp')==s.ctx.resources.current('fly','hp')==12689;assert s.ctx.resources.current('off_axis','hp')==24689;assert not s.ctx.alive('player') and s.ctx.resources.current('player','hp')==24689;assert not s.ctx.alive('trap') and s.ctx.resources.current('trap','hp')==0
 issued=events(s,'depletion.cast.issued');assert len(issued)==1 and issued[0][0]==83;assert issued[0][1]['finish_at']==128 and issued[0][1]['permit']['ability']=='ability/ch9/pillar/collapse_'+direction
 for alias in ['ground','fly']:
  b=next(b for b in s.ctx.get(alias,('buffs','instances')) if b['definition']=='buff/ch9/pillar/stun10');assert b['started_at']==128 and b['expires_at']==428
 tokens=events(s,'tile.token_created');assert len(tokens)==2
 for t,x in tokens:
  assert t==128;assert s.ctx.alive(x['token']);assert s.ctx.resources.current(x['token'],'hp')==100;assert s.ctx.attributes.value(x['token'],'block_count')==3;assert s.ctx.get(x['token'],('ownership','owner'))==s.session.world.resolve('pillar')


def test_real_source_outside_x5_rejects_health_depletion_and_cast():
 s=proof(scene(outside=True),'outside_source',[14,74],131);assert not events(s,'command.rejected');assert s.ctx.resources.current('pillar','hp')==5000;assert s.ctx.depletion.state(s.session.world.resolve('pillar'))['stage']=='normal';assert not events(s,'depletion.started');assert not events(s,'depletion.cast.issued');assert not events(s,'tile.token_created')


def test_zero_HP_public_start_fake_cast_and_underlying_timed_dispatch_have_no_authority():
 s=create(scene());s.advance(74);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.abilities.start('pillar','ability/ch9/pillar/collapse_right',automatic=True)
 assert s.checkpoint()==before;s.advance(16);before=s.checkpoint();cast=next(iter(s.ctx.get('pillar',('runtime','casts')).values()))
 with pytest.raises(ValueError):
  with s.ctx.depletion.cast_scope(s.session.world.resolve('pillar'),deepcopy(cast)):pass
 assert s.checkpoint()==before
 task=next(t for t in s.session.scheduler.pending if t['kind']=='domain.ability.effect' and t['payload']['source']==s.session.world.resolve('pillar'))
 s.session._handlers['domain.ability.effect'](s.session,deepcopy(task['payload']))
 assert s.checkpoint()==before
 with pytest.raises(ValueError):s.ctx.effects.execute('pillar',['player'],{'op':'retire','parameters':{'reason':'withdrawn'}},cast=deepcopy(cast))
 assert s.checkpoint()==before;assert s.ctx.alive('player')


def test_owned_ruin_blocks_three_actual_route_movers_but_fourth_is_free():
 p=scene();mover=actor('mover',1);mover['components']['spatial']['route']={'motionMode':'WALK','startPosition':{'row':4,'col':5},'endPosition':{'row':5,'col':5},'checkpoints':[]};p['entities'].append(mover);p['scenarioDraft']['scheduledEffects']=[{'at':130,'effect':{'op':'spawn','target':'source','definition':mover['id'],'position':{'row':4,'col':5}}} for _ in range(4)]
 s=proof(p,'owned_ruin_block3',[90,129],133);tokens=events(s,'tile.token_created');first=next(x['token'] for _,x in tokens if x['cell']=={'row':4,'col':5});movers=[e['id'] for e in s.session.world.entities() if e['definition_id']==mover['id']];assert len(movers)==4;assert [s.ctx.spatial.blocked_by(x) for x in movers]==[first,first,first,None]


def test_actual_frozen_full_source_module_and_current_core_guard():
 assert guard()==START;assert all(sha(__import__('pathlib').Path(k))==v for k,v in SOURCE_LOCKS.items())
