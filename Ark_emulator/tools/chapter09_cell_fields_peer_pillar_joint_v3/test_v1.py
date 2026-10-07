from tools.chapter09_cell_fields_peer_pillar_joint_v3.fixture import *
from ark_sim.contracts import thaw,digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest,json

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=251005)
def events(s,kind):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==kind]
def proof(p,name,split,end):
 a=create(p);a.advance(split);LOG.mkdir(parents=True,exist_ok=True);path=LOG/(name+'.checkpoint.json');pin=write_ordered(path,a.checkpoint());b=Engine.restore(a.program,load_bound(path,pin),providers=REG);a.advance(end-split);b.advance(end-split);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot()
 REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'runtime':CORE,'actual_CP_head_full_equal':True,'CP_SHA':pin,'input_digest':digest(p),'events':len(a.session.events)},indent=2),encoding='utf8');return a

def test_same_road_key_different_bound_boards_membership_leave_and_source_none_infection():
 p=synthetic();p['entities'][2]['components']['selection_state']['abnormal_flags']=[0];a=create(p);assert [a.ctx.attributes.value(x,'base_force_level') for x in ['ground','fly','enemy','mechanism','plain']]==[6.25,6.25,5.25,5.25,5.25]
 s=proof(p,'road_distinct_boards',29,65);assert not events(s,'command.rejected');assert s.ctx.attributes.value('ground','base_force_level')==5.25;assert s.ctx.attributes.value('fly','base_force_level')==6.25;assert s.ctx.attributes.value('plain','base_force_level')==5.25;assert s.ctx.resources.current('infection_fly','hp')==54321;assert s.ctx.resources.current('infected','hp')==53961
 hits=events(s,'damage.accepted');assert [(t,x['source'],x['amount']) for t,x in hits]==[(30,None,180),(60,None,180)];assert all(x['environmental'] and x['ignore_for_sp'] and x['source_policy']=='none' for _,x in hits)
 buffs=[b for b in s.ctx.get('infected',('buffs','instances')) if b['definition']=='buff/ch8/environment/tile_infection'];assert len(buffs)==1 and buffs[0]['expires_at']==9000;assert s.ctx.attributes.value('infected','atk')==775.5;assert s.ctx.attributes.value('infected','attack_speed_ratio')==1.9
 fields=s.ctx.state()['tile_fields'];assert set(fields)=={'1:2','2:3'};assert fields['1:2']['tile_key']==fields['2:3']['tile_key']=='tile_road';assert fields['1:2']['source_blackboard']!=fields['2:3']['source_blackboard']

def test_shared_two_actual_field_owners_first_retire_last_leave_no_stacking():
 p=synthetic();p['scenarioDraft']['commands']=[];extra={'definition':'unit/ch9/bigforce/field','instanceAlias':'extra_field','position':{'row':1,'col':2}};p['scenarioDraft']['initialEntities'].append(extra);extra_id=len(p['scenarioDraft']['initialEntities'])+1;controller=actor('director');controller['components']['abilities']=['ability/peer/retire_extra'];p['entities'].append(controller);p['abilities'].append({'id':'ability/peer/retire_extra','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'retire','target':extra_id,'parameters':{'reason':'withdrawn'}}}]});p['scenarioDraft']['initialEntities'].append({'definition':controller['id'],'instanceAlias':'director','position':{'row':0,'col':0}});p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'director','ability':'ability/peer/retire_extra'},{'at':4,'action':'skill','source':'ground','ability':'ability/peer/leave'}]
 a=create(p);assert a.session.world.resolve('extra_field')==extra_id;child=[b for b in a.ctx.get('ground',('buffs','instances')) if b['definition']=='buff/ch9/bigforce/base_force'];assert len(child)==1 and len(child[0]['aura_leases'])==2;assert a.ctx.attributes.value('ground','base_force_level')==6.25;a.advance(3);child=[b for b in a.ctx.get('ground',('buffs','instances')) if b['definition']=='buff/ch9/bigforce/base_force'];assert len(child)==1 and len(child[0]['aura_leases'])==1;assert a.ctx.attributes.value('ground','base_force_level')==6.25
 s=proof(p,'multiple_owners',3,7);assert not events(s,'command.rejected');assert s.ctx.attributes.value('ground','base_force_level')==5.25;assert not any(b['definition']=='buff/ch9/bigforce/base_force' for b in s.ctx.get('ground',('buffs','instances')))

def test_illegal_cell_identity_profile_and_unbound_source_operands_reject():
 bad=[]
 for key in ['01:2','-1:2','1:04','3:0','1:99','a:2']:
  p=synthetic();p['scenarioDraft']['map']['tile_cell_mechanics']={key:force_profile()};bad.append(p)
 p=synthetic();p['scenarioDraft']['map']['tile_cell_mechanics']['1:2']['type']='route_checkpoint_portal';bad.append(p)
 p=synthetic();p['scenarioDraft']['map']['tiles'][6]['blackboard'][0]['value']=True;bad.append(p)
 p=synthetic();p['scenarioDraft']['map']['tiles'][6]['blackboard'].append({'key':'unbound_peer_operand','value':7.0});bad.append(p)
 p=synthetic();p['scenarioDraft']['map']['tiles'][6]['blackboard'][0]['valueStr']='1';bad.append(p)
 for p in bad:
  with pytest.raises(ValueError):Compiler(providers=REG).compile(p)


def test_field_static_role_cannot_be_overridden_into_combat_or_dynamic_owner():
 p=synthetic();next(x for x in p['entities'] if x['id']=='unit/ch9/bigforce/field')['tags'].append('player')
 with pytest.raises(ValueError):Compiler(providers=REG).compile(p)
 p=synthetic();p['scenarioDraft']['initialEntities'].append({'definition':'unit/ch9/bigforce/field','position':{'row':0,'col':0},'components':{'spatial':{'motion_mode':1}}})
 with pytest.raises(ValueError):Compiler(providers=REG).compile(p)
 p=synthetic();p['scenarioDraft']['initialEntities'].append({'definition':'unit/ch9/bigforce/field','position':{'row':0,'col':0},'parameters':{'owner':2}})
 with pytest.raises(ValueError):Compiler(providers=REG).compile(p)


def test_native_maps_keep_all_keys_fields_and_repeated_alias_record_identity():
 maps=json.loads(MAPS.read_bytes())['maps'];native=json.loads(NATIVE.read_bytes())['stages'];m=maps['level_main_09-16'];raw=native['level_main_09-16']['native_document'];assert [t['tileKey'] for t in m['tiles']]==[raw['mapData']['tiles'][idx]['tileKey'] for row in raw['mapData']['map'] for idx in row];assert set(m['tile_cell_mechanics'])=={'1:6','5:6','5:7','6:6'};assert m['tiles'][67]['tileKey']=='tile_floor' and m['tiles'][78]['tileKey']=='tile_wall'
 regs=registrations('level_main_09-16',raw,{'trap_043_dupilr':'unit/peer/native_pillar_reference'});assert regs['aliases']['trap_043_dupilr#1']==['level_main_09-16/tokenInsts/'+str(i) for i in range(3)];assert len({r['registration_key'] for r in regs['records']})==3
 with pytest.raises(ValueError):resolve_reference(regs,alias='trap_043_dupilr#1')
 assert resolve_reference(regs,record_key='level_main_09-16/tokenInsts/2')=='level_main_09-16/tokenInsts/2'
 p=package();a=actor('native_force');a['components']['abilities']=[];p['entities'].append(a);p['scenarioDraft']={'id':'scene/peer/native_force_map','ruleset':'ruleset/ark_standard','map':deepcopy(m),'initialEntities':[{'definition':a['id'],'instanceAlias':'native_force','position':{'row':5,'col':7}}]};s=proof(p,'native_0918_map',1,4);assert s.ctx.attributes.value('native_force','base_force_level')==6.25;assert set(s.ctx.state()['tile_fields'])=={'1:6','5:6','5:7','6:6'}
 p=package();a=actor('native_road');a['components']['abilities']=[];p['entities'].append(a);p['scenarioDraft']={'id':'scene/peer/native_infection_map','ruleset':'ruleset/ark_standard','map':deepcopy(maps['level_main_09-17']),'initialEntities':[{'definition':a['id'],'instanceAlias':'native_road','position':{'row':3,'col':6}}]};s=proof(p,'native_0919_road',29,65);assert [(t,x['source'],x['amount']) for t,x in events(s,'damage.accepted')]==[(30,None,180),(60,None,180)];assert s.ctx.spatial.grid.tile(3,6)['tileKey']=='tile_road'


def test_runtime_source_and_four_delta_guard():
 assert guard()==START
 frozen=json.loads((ROOT/'validation/campaign/chapter09_depletion_peer_joint_v3/identity.freeze.json').read_bytes());assert frozen['core_before']==frozen['core_after']==CORE
 for item in frozen['delta']:assert sha(CAND/item['path'])==item['candidate_sha256']
 assert sha(ROOT/'validation/campaign/chapter09_pillar_channel_joint_v3/merge.json')==frozen['joint_merge_sha']
