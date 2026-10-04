"""Current Mon3tr range-defense and other-killer marker boundary witnesses."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import witness_deployed_six as output
from tools import witness_canonical_kalts as k


def setup(data):
    enemy = next(e for e in data['entities'] if e['id'] == 'unit/kalts_witness_enemy')
    for label,effect in [('physical',{'op':'damage','damage_type':'physical'}),
        ('outside',{'op':'move','position':{'row':0,'col':0}}),
        ('inside',{'op':'move','position':{'row':4,'col':5}})]:
        aid = 'ability/kalts_boundary_'+label
        enemy['components']['abilities'].append(aid)
        data['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},
            'selector':'selector/kalts_witness_mon','timeline':[{'at':0,'effect':effect}]})
    return data


def defense_range(skill):
    data = setup(k.base(sp=15 if skill else 0,near=False))
    sim = k.h.make(data)
    k.summon(sim)
    if skill:
        k.h.command(sim,'host','ability/kalts_host_s3')
    for tick,name in [(1,'physical'),(2,'outside'),(3,'physical'),(4,'inside'),(5,'physical')]:
        k.h.command(sim,'enemy','ability/kalts_boundary_'+name,at=tick)
    sim.advance(6)
    uid = k.mon(sim)
    hits = output.events(sim,'damage.accepted','enemy','ability/kalts_boundary_physical')
    assert [e['time'] for e in hits] == [1,3,5]
    expected = [50,1000,50] if skill else [1000-389,1000,1000-389]
    for e,value in zip(hits,expected):
        output.eq(e['payload']['amount'],value)
    output.eq(sim.ctx.resources.current(uid,'hp'),5177-sum(expected))
    assert not output.events(sim,'command.rejected')
    return output.finish(sim,{'in_out_in_physical_damage':expected,
        'base_DEF':389,'S3_direct_DEF_multiplier':3 if skill else 1,
        'outside_final_DEF':0,'minimum_physical_damage_ratio':.05,'client_comparator_pending':True})


def other_killer_keeps_no_kill_penalty():
    data = k.base(sp=15,near=False,enemy_hp=1)
    data['entities'].append({'id':'unit/kalts_boundary_friend','kind':'entity','tags':['player'],
        'components':{'attributes':{'base':{'atk':10000}},'spatial':{},'abilities':['ability/kalts_boundary_friend_kill']}})
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/kalts_boundary_friend','instanceAlias':'friend','position':{'row':8,'col':8}})
    data['selectors'].append({'id':'selector/kalts_boundary_enemy','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1})
    data['abilities'].append({'id':'ability/kalts_boundary_friend_kill','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/kalts_boundary_enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true'}}]})
    sim = k.h.make(data)
    k.summon(sim)
    k.h.command(sim,'host','ability/kalts_host_s3')
    k.h.command(sim,'friend','ability/kalts_boundary_friend_kill',at=1)
    sim.advance(2)
    uid = k.mon(sim)
    kills = output.events(sim,'combat.kill')
    assert len(kills) == 1 and kills[0]['payload']['source'] == sim.session.world.resolve('friend')
    assert sim.ctx.resources.current(uid,'no_kill') == 1
    sim.advance(599)
    output.eq(sim.ctx.resources.current(uid,'hp'),5177*.5)
    assert sim.ctx.resources.current(uid,'no_kill') == sim.ctx.resources.current(uid,'mode') == 0
    return output.finish(sim,{'foreign_killer_does_not_clear_owned_marker':True,
        'skill_duration_ticks':600,'penalty_HP':5177*.5,'client_callback_order_pending':True})


CASES = {'normal_defense_inside_outside_reentry':lambda:defense_range(False),
    's3_defense_inside_outside_reentry':lambda:defense_range(True),
    'other_killer_keeps_no_kill_penalty':other_killer_keeps_no_kill_penalty}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',action='append',choices=list(CASES))
    args = parser.parse_args()
    package = ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json'
    k.h.PACKAGE = package
    from ark_sim.adapters.api import implementation_digest
    files = [package,Path(__file__),ROOT/'tools/witness_deployed_six.py',ROOT/'tools/witness_canonical_kalts.py',
        ROOT/'tools/canonical_summon_witness_support.py',ROOT/'packages/campaign/skills.kalts.json',
        ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/talents.support.json']
    before = {str(p):output.sha(p) for p in files}
    core = implementation_digest()
    result = {'schema':'ark-sim/kalts-boundary-witnesses/v1','passed':False,
        'implementation_sha256':core,'input_package_sha256':output.sha(package),
        'selected_cases':args.case or list(CASES),'cases':{},'identity_at_start':before,'formal_approval':False}
    for name in result['selected_cases']:
        try:
            result['cases'][name] = CASES[name]()
            print(json.dumps({'case':name,'passed':True}),flush=True)
        except Exception as error:
            result['failure'] = {'case':name,'error':repr(error)}
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            raise
    after = {str(p):output.sha(p) for p in files}
    assert before == after and core == implementation_digest()
    result.update(passed=True,identity_stable=True,identity_at_completion=after,
        tests=[{'path':Path(__file__).relative_to(ROOT).as_posix(),'source_sha256':output.sha(Path(__file__)),'result':'passed'}])
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


if __name__ == '__main__':
    main()
