import copy,pytest
from tools.chapter08_terminal_lifecycle.test_terminal_source_v6 import package,providers,Compiler,Engine
from ark_sim.domains.terminal_lifecycle import valid,authorize

def make(p=None):
 p=p or package();reg=providers();pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg,seed=817);s.submit({'action':'skill','source':'player','ability':'ability/counter/kill'},at=1);s.submit({'action':'skill','source':'player','ability':'ability/counter/kill'},at=160);return pr,s,reg

@pytest.mark.parametrize('field,value',[('counts',[True]),('counts',[2,2]),('duration_seconds',True),('duration_seconds',float('inf')),('duration_seconds',0),('owned_abilities',[]),('owned_abilities',['ability/counter/kill']),('retained_buffs',['buff/not_exists'])])
def test_schema_finite_owned_typed(field,value):
 p=package();p['entities'][0]['components']['rebirth']['zero_restore_lifecycle'][field]=value
 with pytest.raises(Exception):Compiler(providers=providers()).compile(p)

def test_manual_or_direct_automatic_cannot_borrow_terminal_window():
 pr,s,reg=make();s.advance(320);ref=s.session.world.resolve('boss');assert valid(s.ctx,ref)
 before=s.checkpoint()
 for automatic in (True,False):
  with pytest.raises(ValueError):authorize(s.ctx,ref,'ability/terminal/screen10',automatic)
 assert s.checkpoint()==before
 s.submit({'action':'skill','source':'boss','ability':'ability/terminal/screen10'},at=321);s.advance(3)
 assert any(e['type']=='command.rejected' and e['time']==321 for e in s.session.events)

@pytest.mark.parametrize('change',['bool_generation','bool_life','missing_job','wrong_deadline','health_nonzero'])
def test_real_job_incarnation_and_HP0_required(change):
 pr,s,reg=make();s.advance(320);ref=s.session.world.resolve('boss');state=s.ctx.get(ref,('runtime','rebirth'));assert valid(s.ctx,ref)
 if change=='bool_generation':state['terminal']['generation']=True
 elif change=='bool_life':state['terminal']['incarnation']['life']=False
 elif change=='wrong_deadline':state['terminal']['due_at']+=1
 elif change=='missing_job':s.session.cancel(state['terminal']['task'])
 else:
  hp=s.ctx.get(ref,('resources','hp'));hp['current']=1;s.ctx.set(ref,('resources','hp'),hp)
 s.ctx.set(ref,('runtime','rebirth'),state);assert valid(s.ctx,ref) is None

def test_terminal_enter_callback_fault_rolls_back_and_clears_scope():
 p=package();p['entities'][0]['components']['rebirth']['zero_restore_lifecycle']['on_enter'].append({'op':'modify_resource','target':'source','resource':'not_real','delta':1});pr,s,reg=make(p);s.advance(310)
 with pytest.raises(Exception):s.advance(1)
 assert s.ctx.resources.current('boss','hp')==0 and s.ctx.get('boss',('runtime','rebirth','phase'))=='waiting'
 assert not getattr(s.ctx.rebirth,'_terminal_entering',[]) and not getattr(s.ctx.rebirth,'_self_buff_finishing',[])
 assert not [e for e in s.session.events if e['type']=='entity.terminal.started']
 assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.rebirth.terminal_end']

def test_undeclared_exactzero_remains_rejected():
 p=package();p['entities'][0]['components']['rebirth'].pop('zero_restore_lifecycle');pr,s,reg=make(p);s.advance(310)
 with pytest.raises(ValueError,match='positive finite'):s.advance(1)
 assert s.ctx.get('boss',('runtime','rebirth','phase'))=='waiting'
