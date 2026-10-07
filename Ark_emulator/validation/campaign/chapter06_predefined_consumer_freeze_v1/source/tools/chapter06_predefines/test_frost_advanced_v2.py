"""Source periodic/duration/native branch boundary supplement on frozen read-only a705."""
import json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from tools.chapter06.cold.policies import providers
from tools.chapter06_predefines.test_frost_consumer_v3 import package,flags,events,CORE
from ark_sim.adapters.api import implementation_digest
def make(p):
 reg=providers();return Engine.create(Compiler(providers=reg).compile(p),providers=reg)
def test_real_native_branch_is_two_activations_on_existing_instances():
 p=package(two=True);profile=json.loads((ROOT/'packages/campaign/chapter06_predefines_consumer/source.profile.json').read_bytes());p['scenarioDraft']['scheduledEffects']=[];p['scenarioDraft']['branches']={'frstar_frosts':{'loop':False,'phases':[{'pre_delay_seconds':0,'actions':[{'delay_seconds':0,'effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':a}}]} for a in profile['exact_aliases']]}]}};p['scenarioDraft']['scheduledEffects']=[{'at':100,'effect':{'op':'advance_branch','parameters':{'branch':'frstar_frosts'}}}];s=make(p);s.session.advance(110);assert len(events(s,'entity.activated'))==2 and all(e['time']==100 for e in events(s,'entity.activated'))
def test_two_source_fields_sameframe_cold_to_frozen_real_status_and_no_damage():
 p=package(two=True);p['scenarioDraft']['initialEntities'][-1]['position']={'row':3,'col':4};s=make(p);s.session.advance(590);assert 16 in flags(s,'inside_edge') and 23 not in flags(s,'inside_edge');assert s.ctx.resources.current('inside_edge','hp')==2000 and not events(s,'damage.accepted')
def test_native_single_source_repeats_SPcost_only_and_cold_exact_expiry():
 s=make(package());s.session.advance(590);assert 23 in flags(s,'inside_edge');applied=events(s,'buff.applied');cold=[e for e in applied if e['payload'].get('buff')=='buff/ch6/cold/e2c_cold'];assert cold;expires=cold[0]['time']+300;s.session.advance(expires-1-s.session.time);assert 23 in flags(s,'inside_edge');s.session.advance(1);assert not flags(s,'inside_edge');s.session.advance(1100-s.session.time);starts=[e for e in events(s,'ability.started') if e['payload']['ability']=='ability/ch6/predefined/frosts/source_cold'];assert len(starts)==2 and 23 in flags(s,'inside_edge') and 16 not in flags(s,'inside_edge');assert starts[1]['time']-starts[0]['time']==476
def test_side_motion_category_status_resistance_legal_profiles():
 for field,value in [('side',1),('motion',0),('category',4)]:
  p=package();p['entities'][-1]['components']['selection_state'][field]=value;s=make(p);s.session.advance(600);assert not flags(s,'inside_edge')
 p=package();p['entities'][-1]['components']['attributes']['base']['one_minus_status_resistance']=.5;s=make(p);s.session.advance(590);assert 23 in flags(s,'inside_edge');b=[x for x in s.ctx.get('inside_edge',('buffs','instances'),[]) if x['definition']=='buff/ch6/cold/e2c_cold'];assert b and b[0]['expires_at']-b[0]['started_at']==150
