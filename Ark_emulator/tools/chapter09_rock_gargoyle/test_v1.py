"""Fresh isolated consumer + provenance + transaction probes, CP/from-head equality."""
from tools.chapter09_rock_gargoyle.build_v1 import *
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.adapters.api import implementation_digest
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest
TRAIT={'id':'buff/fixture/actual_pillar_trait','kind':'buff','metadata':{'test_only':True,'native_key':'dupilr_trait'}}
LOG=Path('E:/ArkSimLogs/runs/chapter09_rock_gargoyle_v1');REPORT=ROOT/'validation/campaign/chapter09_rock_gargoyle'
def fixture(key,profile='native_reference',pillar=False):
 p=build(key,pillar_trait_buff=TRAIT['id'],dependency_definitions=[TRAIT],restore_profile=profile) if key==KEYS[1] else build(key)
 p['buffs'] += [TRAIT,{'id':'buff/fixture/stun','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_flags':[0]},'control':{'move':False,'attack':False,'abilities':False,'interrupt':True}}]
 p['entities'].append({'id':'unit/fixture/source','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':20000,'atk':10000,'def':137,'mres':23,'block_count':1}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/fixture/strike','ability/fixture/stun'],'buffs':{'initial':[TRAIT['id']] if pillar else []}}})
 p['selectors'].append({'id':'selector/fixture/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]})
 for name,e in [('strike',{'op':'damage','damage_type':'true','scale':1}),('stun',{'op':'apply_buff','buff':'buff/fixture/stun'})]:p['abilities'].append({'id':'ability/fixture/'+name,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/fixture/enemy','timeline':[{'at':0,'effect':e}]})
 p['scenarioDraft']={'id':'scene/rock/'+key+'/'+profile+str(pillar),'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'enemy','position':{'row':0,'col':0}},{'definition':'unit/fixture/source','instanceAlias':'source','position':{'row':0,'col':1}}],'commands':[]}
 return p

def proof(p,name,split,end):
 pr=Compiler(providers=providers()).compile(p);s=Engine.create(pr,providers=providers(),seed=91620);s.advance(split);LOG.mkdir(parents=True,exist_ok=True);cp=LOG/(name+'.json');pin=write_ordered(cp,s.checkpoint());r=Engine.restore(pr,load_bound(cp,pin),providers=providers());s.advance(end-split);r.advance(end-split);head=replay(pr,s.export_replay(),providers=providers());assert s.checkpoint()==r.checkpoint()==head.checkpoint();assert list(s.session.events)==list(r.session.events)==list(head.session.events)
 REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.receipt.json')).write_text(json.dumps({'runtime':implementation_digest(),'CP_head_events_equal':True,'events':len(s.session.events),'CP_sha':pin,'input_sha':hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),'whole_stage':False,'client_verified':False},indent=2),encoding='utf8');return s

def test_dependency_slot_is_required():
 with pytest.raises(ValueError,match='supplied pillar'):build(KEYS[1])
 with pytest.raises(ValueError,match='compiled Buff'):build(KEYS[1],pillar_trait_buff=TRAIT['id'])
@pytest.mark.parametrize('profile,restored',[('native_reference',2000.0000298023224),('prts_reference',10000)])
def test_exact_rebirth_stone_damageable_and_fly(profile,restored):
 p=fixture(KEYS[1],profile);p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/fixture/strike'}];pr=Compiler(providers=providers()).compile(p);s=Engine.create(pr,providers=providers());s.advance(3);assert s.ctx.resources.current('enemy','hp')==pytest.approx(restored);assert s.ctx.attributes.value('enemy','def')==1350;assert s.ctx.attributes.value('enemy','mres')==100;assert s.ctx.resources.current('enemy','mode')==1
 s=proof(p,'stone_fly_'+profile,100,400);assert s.ctx.resources.current('enemy','mode')==2;assert s.ctx.get('enemy',('spatial','motion_mode'))==1;assert s.ctx.attributes.value('enemy','def')==550;assert s.ctx.attributes.value('enemy','mres')==70
@pytest.mark.parametrize('pillar',[False,True])
def test_actual_damage_source_skips_only_pillar(pillar):
 p=fixture(KEYS[1],pillar=pillar);p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/fixture/strike'}];s=proof(p,'pillar_'+str(pillar),1,4)
 assert s.ctx.alive('enemy') is (not pillar);assert s.ctx.resources.current('enemy','mode')==(3 if pillar else 1);assert len([e for e in s.session.events if e['type']=='entity.rebirth.skipped'])==int(pillar)
 assert len([e for e in s.session.events if e['type']=='entity.rebirth.started'])==int(not pillar)
@pytest.mark.parametrize('when',[100,400])
def test_second_lethal_stone_or_flight_is_irreversible(when):
 p=fixture(KEYS[1]);p['scenarioDraft']['commands']=[{'at':t,'action':'skill','source':'source','ability':'ability/fixture/strike'} for t in [2,when]];s=proof(p,'second_zero_'+str(when),when-1,when+5);assert not s.ctx.alive('enemy');assert len([e for e in s.session.events if e['type']=='entity.rebirth.started'])==1

def test_airborne_res0_ranged_physical_and_one_way_landing():
 p=fixture(KEYS[0]);p['scenarioDraft']['commands']=[{'at':30,'action':'skill','source':'source','ability':'ability/fixture/stun'},{'at':60,'action':'skill','source':'source','ability':'ability/fixture/stun'}];s=proof(p,'flight_land',31,95);assert s.ctx.resources.current('enemy','mode')==1;assert s.ctx.get('enemy',('spatial','motion_mode'))==0;assert s.ctx.attributes.value('enemy','mres')==0
 hits=[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted'];assert hits[0]==(17,263);assert len([e for e in s.session.events if e['type']=='native.durokt.break'])==1

def test_skip_result_type_failure_rolls_back_actual_damage():
 p=fixture(KEYS[1]);reg=providers();reg['reference.ch9.source_buff_skip']={'callable':lambda i,p,c:1,'version':'1'};s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.advance(1);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('source',['enemy'],{'op':'damage','damage_type':'true','scale':1})
 assert before==s.checkpoint()

@pytest.mark.parametrize('origin',['unmarked_source','target_only','source_less','expired_source'])
def test_foreign_marker_does_not_forge_actual_source_skip(origin):
 p=fixture(KEYS[1]);s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers());s.advance(1)
 if origin=='target_only':s.ctx.buffs.apply('enemy','enemy',TRAIT['id'])
 if origin=='expired_source':
  s.ctx.buffs.apply('source','source',TRAIT['id'],duration_override=.1);s.advance(4)
 if origin=='source_less':s.ctx.resources.adjust('enemy','hp',value=0)
 else:s.ctx.effects.execute('source',['enemy'],{'op':'damage','damage_type':'true','scale':1})
 assert s.ctx.alive('enemy');assert s.ctx.resources.current('enemy','hp')==pytest.approx(2000.0000298023224)
 assert not [e for e in s.session.events if e['type']=='entity.rebirth.skipped']

def test_missing_and_wrong_kind_skip_rules_fail_compile():
 p=fixture(KEYS[1]);p['entities'][0]['components']['rebirth']['skip_rule']='rule/absent'
 with pytest.raises(ValueError):Compiler(providers=providers()).compile(p)
 p=fixture(KEYS[1]);p['entities'][0]['components']['rebirth']['skip_rule']='rule/ch9/dugago/restore'
 with pytest.raises(ValueError):Compiler(providers=providers()).compile(p)

@pytest.mark.parametrize('control',[False,True])
def test_fly_gate_searches_live_self_buff_not_first_slot(control):
 p=fixture(KEYS[0]);p['buffs'].append({'id':'buff/fixture/disabled','kind':'buff','active_rule':'rule/fixture/never'});p['rules'].append({'id':'rule/fixture/never','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'False'}});p['entities'][0]['components']['buffs']['initial'].insert(0,'buff/fixture/disabled')
 if control:p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/fixture/stun'}]
 s=proof(p,'fly_front_slot_'+str(control),3,30);assert s.ctx.resources.current('enemy','mode')==int(control);assert s.ctx.get('enemy',('spatial','motion_mode'))==(0 if control else 1)

def test_ground_fly_reapply_never_returns_native_airborne_mode():
 p=fixture(KEYS[0]);p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/fixture/stun'}];s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers());s.advance(30);s.ctx.buffs.apply('enemy','enemy','buff/ch9/durokt/fly');s.advance(30);assert s.ctx.resources.current('enemy','mode')==1;assert s.ctx.get('enemy',('spatial','motion_mode'))==0

def test_stone_early_finish_runs_native_chain_but_retire_does_not():
 for retiring in [False,True]:
  p=fixture(KEYS[1]);s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers());s.ctx.resources.adjust('enemy','hp',value=0)
  if retiring:s.ctx.lifecycle.retire('enemy','withdrawn');assert not s.ctx.alive('enemy');assert s.ctx.resources.current('enemy','mode')==1
  else:s.ctx.buffs.remove('enemy','buff/ch9/dugago/stone');assert s.ctx.resources.current('enemy','mode')==2;assert s.ctx.get('enemy',('spatial','motion_mode'))==1

def test_native_ground_melee_no_blocker_keeps_moving():
 p=fixture(KEYS[1]);s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers());s.advance(30);assert s.ctx.behavior.plan(s.session.world.resolve('enemy'))=={'move':True,'attack':False};assert not [e for e in s.session.events if e['type']=='damage.accepted']

@pytest.mark.parametrize('style',['API_set','modify_resource'])
def test_source_bearing_non_damage_cannot_forge_pillar_packet(style):
 p=fixture(KEYS[1],pillar=True);s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers())
 if style=='API_set':s.ctx.resources.adjust('enemy','hp',value=0,source='source')
 else:s.ctx.effects.execute('source',['enemy'],{'op':'modify_resource','resource':'hp','value':0,'parameters':{'operation':'damage','source':'source','target':'enemy'}})
 assert s.ctx.alive('enemy');assert s.ctx.resources.current('enemy','hp')==pytest.approx(2000.0000298023224);assert not [e for e in s.session.events if e['type']=='entity.rebirth.skipped']

def test_mismatched_settlement_context_rejected_before_health_mutation():
 p=fixture(KEYS[1],pillar=True);s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers());before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.resources.adjust('enemy','hp',value=0,source='source',settlement_context={'operation':'damage','source':s.session.world.resolve('source'),'target':s.session.world.resolve('source'),'resource':'hp','ability':None,'cast':None})
 assert s.checkpoint()==before
