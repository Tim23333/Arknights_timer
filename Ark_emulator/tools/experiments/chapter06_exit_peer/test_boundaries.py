import pytest
from tools.experiments.chapter06_exit_peer.test_peer_correct import fixture,make,capture
def test_player_actor_cannot_claim_enemy_credit_and_all_exit_state_rolls_back():
 p=fixture({'base_life_loss':0,'kills_delta':1,'leaks_delta':0});p['entities'][0]['tags']=['player'];s=make(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.lifecycle.exit('actor')
 assert s.checkpoint()==before and s.ctx.active('actor')
def test_capability_in_on_remove_callback_updates_other_actor_without_double_credit():
 p=fixture({'base_life_loss':0,'kills_delta':1,'leaks_delta':0},True);p['entities'][0]['components']['buffs']={'initial':['buff/peer/exit_parent']}
 p['entities'].append({'id':'unit/peer/watcher','kind':'entity','components':{'attributes':{'base':{'max_hp':1000}},'resources':{'hp':{'initial':1000,'capacity_attribute':'max_hp','role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/watcher','instanceAlias':'watcher','position':{'row':0,'col':2}})
 p['buffs']=[{'id':'buff/peer/exit_parent','kind':'buff','on_remove':[{'op':'apply_buff','target':3,'buff':'buff/peer/capacity'}]},{'id':'buff/peer/capacity','kind':'buff','modifiers':[{'attribute':'max_hp','layer':'flat','value':100}]}]
 s=make(p);s.advance(25);capture(s,'exit_onremove_capacity')
 assert not s.ctx.active('actor') and s.ctx.resources.current('actor','hp')==95000 and s.ctx.resources.capacity('watcher','hp')==1100
 assert (s.ctx.state()['kills'],s.ctx.state()['leaks'])==(1,0) and len([e for e in s.session.events if e['type']=='lifecycle.exit_accounted'])==1
 assert not [e for e in s.session.events if e['type']=='combat.kill']
