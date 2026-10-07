"""Source lord consumer bridge to frozen bloodline managed descendants."""
import copy,json,hashlib
from pathlib import Path
from tools.chapter10_remaining_v1 import build as prior
from tools.chapter10_bloodline_v1 import build as blood
ROOT=Path(__file__).resolve().parents[2]
SOURCE=prior.SOURCE
KEY='enemy_1226_dklord_2'
def providers():
    return {**blood.providers(),**prior.providers()}
def build(key=KEY):
    if key!=KEY:raise ValueError('This source bridge requires exact dklord_2 variant')
    chain=blood.build_all()
    mark=copy.deepcopy(next(b for b in chain['buffs'] if b['id']==blood.MARK))
    p=prior.build(key,bloodsucker_mark=mark)
    raw=json.loads(SOURCE.read_bytes())['variants'][key]['native_enemy']['resolved']['talentBlackboard']
    blood.attach_death_source(p['entities'][0],raw)
    for category in ['entities','abilities','buffs','rules','selectors','projectiles']:
        existing={d['id']:d for d in p[category]}
        for d in chain.get(category,[]):
            if d['id'] in existing:
                if existing[d['id']]!=d:raise ValueError('Conflicting source definition '+d['id'])
            else:p[category].append(copy.deepcopy(d));existing[d['id']]=d
    prior.bind_recipients(p)
    meta=p['manifest']['metadata']
    meta['pending']=[];meta['whole_consumer_complete']=True
    meta['source_policy']['deathrattle']='Native BB key/delay with real DEATH Buff and bloodline rules; immediate parent retirement, pending managed descendant at delay1; actual inherited route/wave and source aura removal.'
    meta['bloodline_dependency']={'manifest':copy.deepcopy(chain['manifest']),'builder_sha256':hashlib.sha256(Path(blood.__file__).read_bytes()).hexdigest(),'native_blackboard':raw,'child_definition':blood.entity_id('enemy_1221_dzomg_2'),'count_source':'Native bloodsucker_summon _summonCount=1'}
    p['manifest']['id']='package/ch10/remaining_v2/'+key
    return p
