from tools.chapter09_stage918_peer_v2.audit import *
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest


def test_one_tag_semantic_replacement_only_all_body_scene_source_fields_unchanged():
 old=json.loads((ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v1.life99999.json').read_bytes());new=json.loads(PACKAGE.read_bytes());before=deepcopy(old);after=deepcopy(new);ruin=next(d for d in after['definitions'] if d['id']=='unit/ch9/pillar/ruin');assert ruin['tags']==['ruin','terrain_mechanism'];ruin['tags']=['enemy','ruin'];after['manifest']['metadata'].pop('source_device_classification');after['manifest']['metadata'].pop('classification_parent_sha');assert exact(before,after)
 overlay=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v2.life99999.finite_run_v1.json';assert sha(overlay)=='d7a28fe1fc1a7d0170bbf7e075c97b038ade2f60783b033e442135f68bbf5e69';o=json.loads(overlay.read_bytes());o['manifest']['metadata'].pop('runthrough_parent_sha');o['scenarioDraft']['metadata'].pop('runthrough_profile');assert exact(o,new)
 assert 'unit/ch9/pillar/ruin' not in {v['unit'] for v in new['manifest']['metadata']['variant_bindings'].values()}


def isolated(with_movers=False):
 stage=json.loads(PACKAGE.read_bytes());ruin=deepcopy(next(d for d in stage['definitions'] if d['id']=='unit/ch9/pillar/ruin'));p={'schemaVersion':2,'manifest':{'id':'package/peer/ruin_classification','requires':['preset/ark_standard']},'entities':[ruin],'scenarioDraft':{'id':'scene/peer/ruin_classification','ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':10},'resources':{'life':{'initial':99999,'capacity':99999}},'objectives':{'type':'waves','life_resource':'life'},'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[]},'initialEntities':[{'definition':ruin['id'],'instanceAlias':'ruin','position':{'row':3,'col':4},'deployed':True}],'commands':[]}}
 if with_movers:
  mover={'id':'unit/peer/ruin_mover','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':1881,'atk':181,'def':919,'mres':53,'move_speed':.17,'block_cost':1}},'resources':{'hp':{'initial':1881,'capacity':1881,'role':'health'}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/peer/destroy_device']}};p['entities'].append(mover);p['selectors']=[{'id':'selector/peer/device','kind':'selector','region':{'type':'all'},'filters':[{'tag':'terrain_mechanism'}],'limit':1}];p['abilities']=[{'id':'ability/peer/destroy_device','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/device','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}]
  for i in range(4):p['scenarioDraft']['initialEntities'].append({'definition':mover['id'],'instanceAlias':'m'+str(i),'position':{'row':3,'col':4},'route':{'motionMode':'WALK','startPosition':{'row':3,'col':4},'endPosition':{'row':5,'col':4},'checkpoints':[]}})
  p['scenarioDraft']['commands']=[{'at':10,'action':'skill','source':'m0','ability':'ability/peer/destroy_device'}]
 return p

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=1881919)
def proof(p,label,split,end):
 a=create(p);a.advance(split);LOG.mkdir(parents=True,exist_ok=True);path=LOG/(label+'.checkpoint.json');pin=write_ordered(path,a.checkpoint());b=Engine.restore(a.program,load_bound(path,pin),providers=REG);a.advance(end-split);b.advance(end-split);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(label+'.json')).write_text(json.dumps({'core':CORE,'actual_full_CPP_head_equal':True,'CP_SHA':pin,'full_checkpoint_equal':True},indent=2),encoding='utf8');return a

def test_isolated_terrain_device_alive_no_wave_births_terminal_CPPhead():
 s=proof(isolated(),'isolated_device',1,6);assert s.ctx.state()['finished'] is True;assert s.ctx.alive('ruin');assert s.ctx.resources.current('ruin','hp')==100;assert s.ctx.state().get('kills',0)==0;assert s.ctx.attributes.value('ruin','block_count')==3


def test_real_four_route_movers_block3_device_destroyed_not_native_kill_CPPhead():
 p=isolated(True);s=create(p);s.advance(8);assert [s.ctx.spatial.blocked_by('m'+str(i)) for i in range(4)]==[s.session.world.resolve('ruin')]*3+[None];before=s.ctx.state().get('kills',0);s=proof(p,'realblock3_devicekill',8,15);assert not s.ctx.alive('ruin');assert s.ctx.state().get('kills',0)==before==0;assert all(s.ctx.alive('m'+str(i)) for i in range(4));assert [s.ctx.spatial.blocked_by('m'+str(i)) for i in range(4)]==[None]*4;assert not s.ctx.state()['finished'];assert guard()==START
