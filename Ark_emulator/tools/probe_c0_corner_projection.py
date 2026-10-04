"""Read-only actual half-cell targeting/collision projection counterexample."""
import hashlib
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from ark_sim import Compiler,Engine
    from ark_sim.contracts import thaw
    from ark_sim.adapters.api import implementation_digest
    path=ROOT/'packages/campaign/mainline_models/level_main_00-10.m10.json'
    original=json.loads(path.read_bytes());positions=[{'row':4.5,'col':5},{'row':5.5,'col':5}]
    observations=[]
    for position in positions:
        data=json.loads(path.read_bytes())
        data['scenarioDraft'].update(id='scenario/c0_corner_projection',map={'rows':9,'cols':12},waves=[],scheduledEffects=[],objectives={},
            initialEntities=[{'definition':'unit/char_151_myrtle','instanceAlias':'myrtle','position':{'row':4,'col':4}},
                {'definition':'unit/enemy_1000_gopro','instanceAlias':'enemy','position':position}])
        sim=Engine.create(Compiler().compile(data))
        cell=sim.ctx.spatial.grid._cell(position)
        expected=(math.floor(position['row']+.5),math.floor(position['col']+.5));assert cell==expected
        sim.advance(16)
        attacks=[thaw(e) for e in sim.session.events if e['type']=='attack.accepted']
        observations.append({'position':position,'grid_cell':list(cell),'half_even_projection':[round(position['row']),round(position['col'])],
            'half_up_expected':list(expected),'horizontal_row4_range_should_include':cell[0]==4 and cell[1] in (4,5),
            'actual_attacks':attacks,'runtime_fingerprint':sim.runtime_fingerprint,'program_fingerprint':sim.program.fingerprint,
            'initial_entities':thaw(sim.program.scenario['initialEntities']),'replay_inputs':sim.export_replay()})
    assert len(observations[0]['actual_attacks'])==1 and observations[1]['actual_attacks']==[]
    selector=next(s for s in original['selectors'] if s['id']=='selector/char_151_myrtle/normal_attack')
    result={'schema':'ark-sim/c0-corner-projection-audit/v1','implementation_sha256':implementation_digest(),
        'package_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'native_selector':selector,'observations':observations,
        'source_locations':{'collision':'ark_sim/domains/spatial.py:GridTopology._cell','selection':'ark_sim/presets/providers.py:selector_grid'},
        'policy_gap':'selector half-even differs from collision half-up at exact ties; native comparator unknown',
        'primary_or_packages_modified':False,'formal_approval':False}
    out=ROOT/'validation/campaign/c0_corner_projection.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'positions':positions,'actual_attack_counts':[len(o['actual_attacks']) for o in observations],'output':str(out)}))


if __name__=='__main__':main()
