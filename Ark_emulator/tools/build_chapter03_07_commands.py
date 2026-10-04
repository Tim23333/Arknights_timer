"""Twelve-player rotation, original Sensor and finite native crate cards."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'packages/campaign/runthrough/level_main_03-07.m58.life99999.json'
PIN='64ada01030d12d7c2b9685e03e41165336e67c80eb3074a892dc31263142729b'
OUT=ROOT/'scenarios/campaign/chapter03/03-07/commands.runthrough_v1.json'


def build():
    raw=PACKAGE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Frozen stage input changed')
    p=json.loads(raw);s=p['scenarioDraft'];defs={d['id']:d for d in p['definitions']}
    slots=[('char_151_myrtle','myrtle',0,3,2,'right'),('char_222_bpipe','bpipe',450,4,4,'left'),
      ('char_103_angel','angel',900,2,6,'left'),('char_180_amgoat','amgoat',1560,3,9,'left'),
      ('char_202_demkni','saria',2250,4,8,'left'),('char_128_plosis','plosis',2790,5,6,'left'),
      ('char_003_kalts','kalts',3420,6,2,'right'),('char_107_liskam','liskam',4110,3,5,'left'),
      ('char_010_chen','chen',4860,5,5,'left'),('char_400_weedy','weedy',5580,2,5,'left'),
      ('char_179_cgbird','night',6060,5,6,'left'),('char_358_lisa','lisa',6420,3,9,'left')]
    commands=[{'at':at,'action':'withdraw','source':name} for at,name in [(3950,'myrtle'),(4650,'bpipe'),(5370,'saria'),(5850,'plosis'),(6300,'amgoat')]]
    for name,alias,at,row,col,facing in slots:
        unit='unit/'+name;terrain=defs[unit]['components']['deployable']['terrain'];tile=s['map']['tiles'][row*12+col]
        if tile['buildableType']!=(1 if terrain=='ground' else 2):raise ValueError('Illegal source terrain:'+unit)
        commands.append({'at':at,'action':'deploy','definition':unit,'alias':alias,'position':{'row':row,'col':col},'facing':facing})
        commands.append({'at':at+720,'action':'skill','source':alias,'ability':defs[unit]['metadata']['selected_skill_ability']})
    for index,(at,row,col) in enumerate([(1260,2,2),(1860,2,3),(2460,4,2),(3060,5,2),(3660,6,4)]):
        if s['map']['tiles'][row*12+col]['buildableType']!=1:raise ValueError('Illegal native crate position')
        commands.append({'at':at,'action':'deploy','definition':'unit/ch3/crate','alias':'crate'+str(index),'position':{'row':row,'col':col}})
    commands.extend({'at':at,'action':'skill','source':'native_sensor','ability':'ability/sensor/reveal'} for at in (680,2000,4000,6200))
    commands += [
       {'at':3720,'action':'skill','source':'kalts','ability':'ability/kalts_summon','position':{'row':4,'col':5},'facing':'left'},
       {'at':5640,'action':'skill','source':'weedy','ability':'ability/campaign_weedy_deploy_cannon','position':{'row':2,'col':4},'facing':'left'},
       {'at':6500,'action':'skill','source':'night','ability':'ability/support_night_bird','position':{'row':4,'col':4},'facing':'left'}]
    commands.extend({'at':7800+i,'action':'withdraw','source':alias} for i,(_,alias,*_) in enumerate(slots))
    commands.extend({'at':7820+i,'action':'withdraw','source':'crate'+str(i)} for i in range(5))
    return sorted(commands,key=lambda c:c['at'])


if __name__=='__main__':
    commands=build();raw=(json.dumps(commands,ensure_ascii=False,indent=2)+'\n').encode('utf8');OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_bytes(raw)
    print(json.dumps({'commands':len(commands),'player_deployments':12,'native_card_attempts':5,'sha256':hashlib.sha256(raw).hexdigest(),
      'scope':'Public attempts; actual SP/DP/capacity and all outcomes recorded; no guaranteed skill or summon acceptance'}))
