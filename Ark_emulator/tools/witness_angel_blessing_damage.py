"""Friend blessing actual attack/health capacity before and after source exit."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import witness_deployed_six as h
from tools.witness_deployed_offensive import high_tile


def run():
    data = h.scene([h.actor('myrtle',0,hp=1000)],enemies=[(4,5)])
    high_tile(data,4,3)
    data['entities'].append({'id':'unit/blessing_healer','kind':'entity','tags':['fixture'],
        'components':{'attributes':{'base':{'atk':99999}},'spatial':{},'abilities':['ability/blessing_heal']}})
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/blessing_healer','instanceAlias':'probe','position':{'row':0,'col':0}})
    data['selectors'].append({'id':'selector/blessing_myrtle','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'profession:PIONEER'},{'state':'alive'}],'limit':1})
    data['abilities'].append({'id':'ability/blessing_heal','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/blessing_myrtle','timeline':[{'at':0,'effect':{'op':'heal'}}]})
    sim = h.make(data)
    sim.submit({'action':'deploy','entity':'unit/char_103_angel','alias':'angel',
        'position':{'row':4,'col':3},'facing':'right'},at=0)
    h.command(sim,'probe','ability/blessing_heal',at=1)
    sim.submit({'action':'withdraw','source':'angel'},at=16)
    sim.advance(55)
    hits = h.events(sim,'damage.accepted','myrtle','ability/char_151_myrtle/normal_attack')
    # Native base interval1.3s =>39 ticks, windup .5s =>15 ticks.
    assert [e['time'] for e in hits] == [15,54]
    for e,value in zip(hits,[520*1.06-50,520-50]):
        h.eq(e['payload']['amount'],value)
    heals = h.events(sim,'healing.accepted','probe')
    assert len(heals) == 1 and heals[0]['time'] == 1
    h.eq(heals[0]['payload']['amount'],1565*1.1-1000-25/30)
    pulses = [e for e in h.events(sim,'regeneration.accepted') if e['time'] == 1]
    assert len(pulses) == 1 and pulses[0]['id'] < heals[0]['id']
    h.eq(sim.ctx.resources.current('myrtle','hp'),1565)
    assert not h.events(sim,'command.rejected')
    return h.finish(sim,{'friend_attack_before_after':[501.2,470],
        'friend_base_maxHP':1565,'blessed_maxHP':1721.5,'heal_clamps_to_blessed_capacity':721.5-25/30,
        'tick1_regen_precedes_heal':25/30,'friend_attack_ticks':[15,54],
        'source_exit_absolute_HP_clamps_to_base':1565,'native_HP_policy_pending':True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    from ark_sim.adapters.api import implementation_digest
    files = [h.PACKAGE,Path(__file__),ROOT/'tools/witness_deployed_six.py',ROOT/'tools/witness_deployed_offensive.py',
        ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/skills.angel.json',
        ROOT/'packages/campaign/talents.attack.json']
    before = {str(p):h.sha(p) for p in files};core = implementation_digest()
    result = {'schema':'ark-sim/angel-blessing-damage-witness/v1','passed':False,
        'implementation_sha256':core,'input_package_sha256':h.sha(h.PACKAGE),
        'selected_cases':['friend_damage_capacity_source_exit'],'identity_at_start':before,'formal_approval':False}
    try:
        result['cases'] = {'friend_damage_capacity_source_exit':run()}
    except Exception as error:
        result['failure'] = {'error':repr(error)}
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        raise
    after = {str(p):h.sha(p) for p in files}
    assert before == after and core == implementation_digest()
    result.update(passed=True,identity_stable=True,identity_at_completion=after,
        tests=[{'path':Path(__file__).relative_to(ROOT).as_posix(),'source_sha256':h.sha(Path(__file__)),'result':'passed'}])
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':True,'output':str(args.output)}))


if __name__ == '__main__':
    main()
