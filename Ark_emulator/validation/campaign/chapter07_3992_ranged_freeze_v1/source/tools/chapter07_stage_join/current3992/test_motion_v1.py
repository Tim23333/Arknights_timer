import json
from tools.chapter07_stage_join.current3992.probe_sotisp_current import ROOT,package as sniper_package,providers
from tools.chapter07_stage_join.current3992.probe_soticn_current import package as mortar_package,REG
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter07_3992_motion'
def run(p,reg,actor,target,at,end,label):
 p['selectors'].append({'id':'selector/motion/exact','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':target}}]});aid='ability/motion/public';p['abilities'].append({'id':aid,'kind':'ability','selector':'selector/motion/exact','activation':{'mode':'manual'},'timeline':[{'at_seconds':0,'effect':{'op':'set_motion_mode','value':1}}]});p['entities'][0]['components']['abilities'].append(aid);program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);s.submit({'action':'skill','source':actor,'ability':aid},at=at);s.advance(at);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/(label+'.cp.json');assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(end-at);r.advance(end-at);assert s.checkpoint()==r.checkpoint()==replay(program,s.export_replay(),providers=reg).checkpoint();assert s.ctx.entity(target)['components']['selection_state']['motion']==2;assert s.ctx.entity(target)['components']['spatial']['motion_mode']==1;assert any(e['type']=='command.accepted' for e in s.session.events);(OUT/(label+'.trace.json')).write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2),encoding='utf8');return s

def test_sniper_public_ground_to_fly_inflight_capture_hit_but_future_acquisition_reject():
 p=sniper_package();p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:2];s=run(p,providers(),'sniper',3,22,110,'sniper22');assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(24,229)];assert [e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability'].startswith('ability/ch7/')]==[0]
def test_mortar_public_ground_to_fly_inflight_box_live_projection_and_future_reject():
 p=mortar_package();s=run(p,REG,'mortar',3,20,180,'mortar20');assert [(e['time'],e['payload']['target'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(46,3,339),(46,4,339)];assert [e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability'].startswith('ability/ch7/')]==[0]
