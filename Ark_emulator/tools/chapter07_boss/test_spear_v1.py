"""Actual tile-qualified source spear and alive Immo; partial-source scope."""
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter07_boss.test_mechanism_v5 import package as original,deploy,kill,ev
from tools.chapter07_boss.build_mechanism_v1 import OUT,UID
from tools.chapter07_boss.build_mechanism_v4 import SPEAR,IMMO,TIMER
from tools.chapter07_boss.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def package():
 probe=original();p=json.loads((OUT/'mechanism.v4.json').read_bytes());p['entities']+=probe['entities'][1:];p['abilities']+=probe['abilities'][2:];p['selectors']+=probe['selectors'][3:];p['scenarioDraft']=probe['scenarioDraft']
 # Exact public killer selector/ability, independent of modulelist offsets.
 for key in ['abilities','selectors']:
  for d in probe[key]:
   if d['id'].startswith(('ability/test/','selector/test/')) and d['id'] not in {x['id'] for x in p[key]}:p[key].append(d)
 for e in p['entities'][0]['components']['ability_arbitration']['entries']:
  if e['ability']!=SPEAR:e['condition']='False'
 for name,col,taunt in [('ground_far',6,1000000000),('high_near',4,0),('high_far',5,0)]:
  p['entities'].append({'id':'unit/test/patrt/'+name,'kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100000,'atk':0,'def':100,'mres':0,'taunt_level':taunt}},'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/test/patrt/'+name,'instanceAlias':name,'position':{'row':2,'col':col}})
 p['scenarioDraft']['map']['tiles']=[{'buildableType':2 if (r,c) in [(2,4),(2,5)] else 1,'passableMask':1} for r in range(5) for c in range(7)]
 return p
def make(p=None):return Engine.create(Compiler(providers=providers()).compile(p or package()),providers=providers(),seed=7187)
def test_actual_highground_mask_ignores_huge_ground_taunt_and_uses_farther_high():
 s=make();a=s.program.definitions[SPEAR];ids=s.ctx.spatial.select('boss',a['selector'],ability=a);assert ids==[s.session.world.resolve('high_far')]
def test_actual_hate_first_lex_not_finitepriority_constant():
 p=package();u=next(u for u in p['entities'] if u['id'].endswith('/high_near'));u['components']['attributes']['base']['taunt_level']=1;s=make(p);a=s.program.definitions[SPEAR];assert s.ctx.spatial.select('boss',a['selector'],ability=a)==[s.session.world.resolve('high_near')]
def test_actual_public_rebirth_then_spear15_skill51_halfsecond_expiry_135percent():
 s=make();deploy(s);kill(s,5);s.session.advance(2256)
 starts=[e for e in ev(s,'ability.started') if e['payload']['ability']==SPEAR];assert len(starts)==1 and starts[0]['time']==2255 and list(starts[0]['payload']['targets'])==[s.session.world.resolve('high_far')]
 s.session.advance(51);launch=[e for e in ev(s,'projectile.launched')];assert len(launch)==1 and launch[0]['time']==2306
 s.session.advance(15);packets=[e for e in ev(s,'damage.accepted') if e['payload'].get('target')==s.session.world.resolve('high_far')];assert len(packets)==1 and packets[0]['time']==2321 and packets[0]['payload']['amount']==2924
def test_actual_alive_rage_immo_single_sourcearea_all_ground_targets_per24ticks():
 s=make();deploy(s);kill(s,5);s.session.advance(1854)
 pulses=[e for e in ev(s,'ability.started') if e['payload']['ability']==IMMO];assert [e['time'] for e in pulses]==[1829,1853]
 packets=[e for e in ev(s,'damage.accepted') if e['payload'].get('target')==s.session.world.resolve('hero') and e['payload'].get('source')==s.session.world.resolve('boss')];assert len(packets)==2 and all(e['payload']['amount']==pytest.approx(2240*.0521) for e in packets)
@pytest.mark.parametrize('tick',[2256,2307])
def test_actual_spear_preflight_or_inflight_diskcp_publichead(tick,tmp_path):
 s=make();deploy(s);kill(s,5);s.session.advance(tick);p=tmp_path/'spear.json';pin=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,pin),providers=providers());s.session.advance(2322-tick);r.session.advance(2322-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
