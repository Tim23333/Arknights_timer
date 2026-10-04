import json
from copy import deepcopy
import pytest
from tools.experiments.chapter06_boss_peer.test_source_final_fixture import fixture,make,deploy,ev,capture,ROOT,PREFIX,BOSS
from tools.campaign_content_composition_v2 import compose_modules

@pytest.mark.parametrize('source',['ordinary','story'])
def test_three_real_gate_targets_one_source_area_three_packets_one_cold_each(source):
 p=fixture(initial={'ability_timing':{'initial_cooldowns':{PREFIX+'burst0':0}}});prefix=PREFIX;aid=PREFIX+'burst0';amount=440;frame=28
 if source=='story':
  s=json.loads((ROOT/'packages/campaign/chapter06_boss/frstar2_s_v3/model.json').read_bytes());cold=json.loads((ROOT/'packages/campaign/chapter06_cold/model.json').read_bytes());peer={'definitions':[d for d in p['definitions'] if d['id'].startswith(('unit/peer/','ability/peer/','buff/peer/','rule/peer/'))]};defs,_=compose_modules([('realStory',s),('cold',cold),('fresh',peer)]);p['definitions']=list(defs.values());prefix='ability/'+s['entities'][0]['id']+'/';aid=prefix+'burst';amount=1200;frame=87;p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:2];p['scenarioDraft']['initialEntities'][0]['definition']=s['entities'][0]['id'];p['scenarioDraft']['initialEntities'][0]['components']={'ability_timing':{'initial_cooldowns':{aid:0}}};p['scenarioDraft'].pop('branches',None)
 owner=next(d for d in p['definitions'] if d['id']=='unit/peer/tank');owner['components']['attributes']['base']['mres']=0
 other=next(d for d in p['definitions'] if d['id']=='unit/peer/other');third=deepcopy(other);third['id']='unit/peer/third';third['components']['attributes']['base']['mres']=40;p['definitions'].append(third);p['scenarioDraft']['roster'].append(third['id'])
 s=make(p);deploy(s,'tank',2,3);deploy(s,'other',3,2);deploy(s,'third',2,1);s.advance(frame+2);capture(s,'three_targets_'+source)
 areas=[e for e in ev(s,'area.resolved') if e['payload'].get('source')==2];hits=[e for e in ev(s,'damage.accepted') if e['payload'].get('ability')==aid];assert len(areas)==1 and len(hits)==3 and sorted(e['payload']['amount'] for e in hits)==pytest.approx(sorted([amount,amount*.83,amount*.6]))
 assert all(e['time']==frame and e['payload']['damage_flags']['source_attack_type']=='SPLASH' for e in hits)
 for name in ['tank','other','third']:
  buffs=s.ctx.get(name,('buffs','instances'),[]);assert [b['definition'] for b in buffs]==['buff/ch6/cold/e2c_cold'] and buffs[0]['expires_at']==frame+300
