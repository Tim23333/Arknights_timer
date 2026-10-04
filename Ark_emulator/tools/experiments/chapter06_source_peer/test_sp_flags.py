from tools.experiments.chapter06_source_peer.test_source_correct import fixture,make,skill,event,capture
def test_native_attack_sp_has_no_charge_when_frozen_source_never_attacks():
 p,c=fixture('snmage_v2');p['definitions'].append({'id':'ability/peer/freeze_source','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':2,'buff':'buff/ch6/cold/e2c_freeze'}]},'timeline':[]})
 for d in p['definitions']:
  if d['id']=='unit/peer/controller':d['components']['abilities'].append('ability/peer/freeze_source')
 s=make(p,c);skill(s,'freeze_source',0);s.advance(120);capture(s,'attack_sp_frozen')
 assert s.ctx.resources.current('adversary','sp')==0 and not [e for e in event(s,'ability.started') if e['payload']['source']==2] and not event(s,'attack.accepted')
def test_source_silence_disables_ready_cold_skill_but_normal_attacks_continue_and_sp_caps_two():
 p,c=fixture('snmage_v2');s=make(p,c);skill(s,'silence_source',0);s.advance(280);capture(s,'ready_source_silenced')
 assert [e['payload']['ability'].split('/')[-1] for e in event(s,'ability.started') if e['payload']['source']==2]==['normal','normal','normal']
 assert [e['payload']['amount'] for e in event(s,'damage.accepted')]==[332,332,332] and s.ctx.resources.current('adversary','sp')==2
 assert not [b for b in s.ctx.get('tank',('buffs','instances'),[]) if b['definition'].startswith('buff/ch6/cold/')]
