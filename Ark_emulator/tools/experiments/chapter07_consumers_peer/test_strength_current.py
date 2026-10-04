import json
from ark_sim import Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.chapter07_consumers_peer.common import *
from tools.campaign_content_composition_v2 import compose_modules
from tools.chapter07_strength_melee.policies_v2 import providers as current_strength_registry
from tools.chapter07_predefines.policies_v1 import providers as ore_registry
def registry():return {**ore_registry(),**current_strength_registry()}
from copy import deepcopy
def create(p,modules):
 definitions,provenance=compose_modules([(str(m),str(m)) for m in modules]);INPUTS.append({'package':deepcopy(p),'modules':[str(m) for m in modules],'composition':provenance});r=registry();return Engine.create(Compiler(providers=r).compile(p,packages={'schemaVersion':2,'definitions':list(definitions.values())}),providers=r,seed=70761)
MARKER='buff/ch7/source/enemy_9D0_talent_strength'
def strength_package(k):
 p=package(k);controller(p,[ability('all_on',[{'op':'apply_buff','target':t,'buff':MARKER} for t in [3,4,5]]),ability('v2_off',[{'op':'remove_buff','target':4,'buff':MARKER}]),ability('others_off',[{'op':'remove_buff','target':t,'buff':MARKER} for t in [3,5]]),ability('v1_dead',[{'op':'modify_resource','target':3,'resource':'hp','value':0}])])
 for i,m in enumerate(STRENGTH):
  src=json.loads(m.read_text(encoding='utf8'));p['scenarioDraft']['initialEntities'].append({'definition':src['entities'][0]['id'],'instanceAlias':'v'+str(i+1),'position':{'row':3,'col':i+1}})
 return p
def derived(s,a):return [b for b in s.ctx.get(a,('buffs','instances'),[]) if b['definition'].startswith('buff/unit/ch7/strength/')]
def test_all_three_actual_variant_derived_ids_and_values_are_owner_scoped():
 p=strength_package('strength_observe');s=create(p,STRENGTH);command(s,'all_on',3);s.advance(9)
 rows=[derived(s,a) for a in ['v1','v2','v3']];assert all(len(x)==1 for x in rows) and len({x[0]['definition'] for x in rows})==3
 assert s.ctx.attributes.value('v1','atk')==540 and s.ctx.attributes.value('v2','atk')==774 and abs(s.ctx.attributes.value('v3','move_speed')-1.43)<1e-10
 for i,m in enumerate(STRENGTH):
  defs=s.program.definitions;d=defs[rows[i][0]['definition']];assert d['modifiers'][0]['value']==[.5,.8,.3][i]
 capture(s,'actual_values_private_observation_no_replay_claim')
def test_variant2_marker_remove_never_cleans_variant1_or_variant3_disk_head(tmp_path):
 p=strength_package('strength_cross');s=create(p,STRENGTH);command(s,'all_on',3);command(s,'v2_off',9);command(s,'others_off',17);s.advance(7);pin=write_ordered(tmp_path/'strength7.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'strength7.json',pin),providers=registry());s.advance(10);r.advance(10)
 assert len(derived(s,'v1'))==len(derived(s,'v3'))==1 and not derived(s,'v2')
 s.advance(9);r.advance(9);h=replay(s.program,s.export_replay(),providers=registry());capture(s,'strength_cp_head');assert s.checkpoint()==r.checkpoint()==h.checkpoint() and all(not derived(s,a) for a in ['v1','v2','v3'])
def test_actual_target_death_one_variant_leaves_other_native_ratios():
 p=strength_package('strength_death');s=create(p,STRENGTH);command(s,'all_on',3);command(s,'v1_dead',10);s.advance(17);capture(s,'variant_death');assert not s.ctx.alive('v1') and not derived(s,'v1') and len(derived(s,'v2'))==len(derived(s,'v3'))==1
