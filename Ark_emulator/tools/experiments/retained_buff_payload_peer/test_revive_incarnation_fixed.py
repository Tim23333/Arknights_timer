import pytest
from tools.experiments.retained_buff_payload_peer.test_peer import fixture,make,capture,INPUTS
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
def revive(inputs,params,context):
 return {'action':'revive','resource':'hp','value':1000,'state':'phase2'} if inputs['resources']['hp']['current']<=0 else {'action':'none'}
revive.version='peer-instant-hpzero-revive-phase2/v1'
@pytest.mark.parametrize('who',[2,3])
def test_actual_lifecycle_hpzero_revive_phase_change_blocks_later_old_packet_application(who):
 p,second=fixture();p['buffs'][0]['effects']=[{'op':'modify_resource','target':who,'resource':'hp','value':0}]
 p['abilities'][0]['activation']['on_start'][0]['on_success'].append(second)
 rule={'id':'rule/peer/instant_revive','kind':'rule','contract':'lifecycle.death','implementation':{'type':'provider','provider':'peer.instant_revive'}}
 p['rules'].append(rule);p['entities'][who-2]['components']['lifecycle']['rules']={'lifecycle.death':rule['id']}
 registry={**BUILTIN_PROVIDERS,'peer.instant_revive':revive};INPUTS.append(deepcopy(p));s=Engine.create(Compiler(providers=registry).compile(p),seed=62011,providers=registry);s.submit({'action':'skill','source':'source','ability':'ability/peer/shot'},at=0)
 try:s.advance(10)
 finally:capture(s,'revive_incarnation_'+str(who))
 assert s.ctx.active(who) and s.ctx.get(who,('runtime','state'))=='phase2' and len([e for e in s.session.events if e['type']=='entity.revived'])==1
 assert [b['definition'] for b in s.ctx.get('target',('buffs','instances'),[])]==['buff/peer/launched']
