import json
from copy import deepcopy
from pathlib import Path
from tools.chapter07_stage_join.current3992.probe_sotisp_current import ROOT,package,Compiler,Engine,providers
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter07_3992_sotisp'
MARKER='buff/ch7/source/enemy_9D0_talent_strength';MODE='buff/model/c7/sotisp/mode1'
def make(p):
 reg=providers();program=Compiler(providers=reg).compile(p);return program,Engine.create(program,providers=reg),reg
def test_plain_exact_source_frame21_cycle75_projectile10_and229():
 p=package();_,s,_=make(p);s.session.advance(110);ev=s.snapshot()['events'];assert [(e['time'],e['payload']['amount']) for e in ev if e['type']=='damage.accepted']==[(24,229),(99,229)];assert [e['time'] for e in ev if e['type']=='ability.started']==[0,75];assert [e['time'] for e in ev if e['type']=='projectile.launched']==[21,96];assert set(s.ctx.entity('sniper')['components']['resources'])=={'hp'}
def test_real_trigger8_enhanced_two_targets_revert24_and_CP7_head():
 p=package();p['selectors'].append({'id':'selector/sniper/source','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':2}}]});p['scenarioDraft']['scheduledEffects']=[{'at':1,'effect':{'op':'apply_buff','buff':MARKER,'selector':'selector/sniper/source'}},{'at':18,'effect':{'op':'remove_buff','buff':MARKER,'selector':'selector/sniper/source'}}];program,s,reg=make(p);s.session.advance(7);assert s.ctx.entity('sniper')['components']['behavior']['state']=='normal';OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'mode7.cp.json';assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.session.advance(105);r.session.advance(105);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay(),providers=reg).snapshot();ev=s.snapshot()['events'];ap=[e for e in ev if e['type']=='buff.applied' and e['payload']['buff']==MODE];rm=[e for e in ev if e['type']=='buff.removed' and e['payload']['buff']==MODE];assert [e['time'] for e in ap]==[8] and [e['time'] for e in rm]==[24];assert s.ctx.entity('sniper')['components']['behavior']['state']=='normal';(OUT/'mode.trace.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2),encoding='utf8')
def test_marker_initial_mode1_selects_two_real_projectiles():
 p=package();p['entities'][0]['components']['buffs']['initial'].append(MARKER);_,s,_=make(p);s.session.advance(110);ev=s.snapshot()['events'];second=[e for e in ev if e['type']=='ability.started' and e['time']>=75];assert len(second)==1 and second[0]['payload']['targets']==[3,4] and second[0]['payload']['ability'].endswith('mode1');assert [(e['time'],e['payload']['target'],e['payload']['amount']) for e in ev if e['type']=='damage.accepted' and e['time']>=75]==[(99,3,229),(102,4,229)]
def test_typed_range_camo_free_fly_excluded():
 for key,value in [('camouflage',True),('target_free',True),('motion',2)]:
  p=package();p['entities'][-1]['components']['selection_state'][key]=value;_,s,_=make(p);s.session.advance(40);assert not [e for e in s.snapshot()['events'] if e['type']=='ability.started']
 p=package();p['scenarioDraft']['initialEntities'][1]['position']['col']=3.21;p['scenarioDraft']['initialEntities'][2]['position']['col']=3.3;_,s,_=make(p);s.session.advance(40);assert not [e for e in s.snapshot()['events'] if e['type']=='ability.started']
