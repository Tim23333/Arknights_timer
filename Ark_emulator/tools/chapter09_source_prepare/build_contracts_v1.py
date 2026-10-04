"""Source preparation only. No runtime imports or simulation claims."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'packages/campaign/chapter09_source_prepare'
FIXED = '56aee3d6c5a29c3a0d192456d70d14252cbb0804'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, value):
    path = BASE / name
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}

def main():
    native = json.loads((BASE / 'ep_breakbuff.fixed56.json').read_bytes())
    detail = json.loads((BASE / 'source.detail.v1.json').read_bytes())
    dump = ROOT.parent / 'Ark_data/Il2CppDumper_current/dump.cs'
    lines = dump.read_text(encoding='utf-8').splitlines()
    excerpts = [{'first_line': a, 'last_line': b, 'text': '\n'.join(lines[a-1:b])}
                for a,b in [(366597,366601),(366797,366813),(386050,386155),(532586,532610),(568416,568533)]]
    write('elemental.schema.excerpts.v1.json', {'schema':'ark-sim/c9-native-ep-schema/v1',
        'source':{'path':str(dump),'sha256':sha(dump)},'excerpts':excerpts,
        'method_bodies_available':False,'warning':'Schema identifies APIs and fields, not their implementation.'})
    policy = {
        'schema':'ark-sim/c9-elemental-policy-source/v1','fixed_commit':FIXED,
        'native':{'fire':native['FIRE'],'buff_closure':'elemental.buff.closure.v1.json',
                  'attack_fields':['Attack._elementDamageType','Attack._epDamageRatio',
                                   'Attack.CreateElementDamageNode(ElementType, FP)'],
                  'Flame':detail['Flame_damage_and_EP'],
                  'deadboom':detail['deadboom_source_beforezero']},
        'reference':{'url':'https://prts.wiki/w/元素','accessed':'2026-10-04',
                     'page_client_version':'2.7.71','native_version_equivalence_verified':False,
                     'defaults':{'capacity':1000,'boss_capacity':2000,'recovery_per_second':0,'resistance_percent':0},
                     'fire':{'character_mres_delta':-20,'character_damage':1200,'character_damage_type':'ARTS',
                             'other_mres_delta':-20,'other_damage':7000,'other_damage_type':'ELEMENT'},
                     'rules':['Independent remaining resources; neutral targets excluded.',
                              'Resistance scales incoming loss; first threshold-crossing packet owns break provenance.',
                              'All element loss and recovery lock during break; expiry restores all capacities.',
                              'Health packet precedes attack-associated elemental packet; buff-specific ordering may differ.'],
                     'replaceable':True},
        'source_binding_policy':'Numeric defaults and global burst amounts are current PRTS reference values, not decoded fixed56 literals. FIRE duration10 and native buff callgraph are separately pinned.',
        'generic_required':{
            'resource_threshold':'Finite content-defined element keys/capacities/rates; validated loss request with source provenance; atomic threshold plan and global recovery lease; public CP/head state includes remaining, break generation and due.',
            'burst_pipeline':'NoSource ART_NORMAL and ELEMENT_NORMAL with original ignoreSP/withoutModify false; apply resistance modifier before first packet. Existing NONE/BUFF-only request must not silently relabel NORMAL.',
            'attack_packet':'Separate health and EP packets use their own scale. Flame source ATK500 yields raw health60 and EP30, not health60*.06.',
            'before_zero':'Owned finite depletion continuation for actual pre-HP-zero source callback; deadlike3s, parallel effects at1s and suicide1.1s. Silence skips continuation. No arbitrary dead-source cast.'},
        'runtime_authored':False,'mechanism_verified':False,'client_verified':False}
    write('elemental.policy.source.v1.json',policy)
    write('generic.interface.design.v1.json',{
        'schema':'ark-sim/c9-content-interface-design/v1','runtime_authored':False,
        'elemental_policy':'elemental.policy.source.v1.json',
        'pillar':{'source':'predefines.native.v3.json','transitive':'duruin.transitive.source.v1.json',
            'reference_url':'https://prts.wiki/w/破碎支柱',
            'contracts':['Before-zero plan binds actual damage source/target lifecycle and native finite buff/action dependencies.',
                         'Direction comes from source relative spatial cell and native mode mapping; exact ties require declared policy.',
                         'Native timed collapse selects two directional cells; damage/force-withdraw/spawn retain separate qualifications.',
                         'Spawned token rewrites terrain/passability using source map-dependent profile and triggers actual route invalidation.',
                         'Ruin HP100/block3 persists until real death/withdraw/terminal cleanup. No fixed lifetime inferred from redeploy5 or spawned visual buff.5.'],
            'parameters':{'pillar_hp':5000,'pillar_atk':12000,'damaged_state_seconds':2,'collapse_payload_predelay':1.5,'stun_seconds':10,'ruin_hp':100,'ruin_block':3},
            'version_conflict':'Token assets official20250327; tables fixed56. Preserve both identities, client alignment unverified.'},
        'registration':{'key':['native_level_id','bucket','record_index'],
            'raw_alias_preserved':True,'duplicate_alias_request':'Reject ambiguous alias unless record reference is supplied.',
            'reason':'9-18 three native tokenInst records all use trap_043_dupilr#1; do not rewrite raw aliases or choose first.'},
        'atomicity':['Validate complete finite dependency set before mutation.','Strict bool distinct from int; all rates/durations finite.','No-op consumes no RNG and writes no state.','Lease/action handles bind lifecycle plus instance/generation; restore cannot borrow stale permission.'],
        'mandatory_probes':['threshold and resistance boundaries','neutral exclusion','all-elements lock and reset','source retire after threshold','silenced vs unsilenced prezero','pillar collapse direction and late occupants','ruin route replan and death cleanup','duplicate aliases and record-index CP/head']})
    write('consumer.assignment.v1.json',{
        'schema':'ark-sim/c9-consumer-assignment/v1','whole_stage_verified':False,
        'stages':[{'display':'9-18','native':'main_09-16','births':34,'waves':1,'routes':25},
                  {'display':'9-19','native':'main_09-17','births':63,'waves':2,'routes':35}],
        'ordered_work':[{'owner':'Root','variants':['duhond','dusbr','dubow'],'dependencies':['silenceable refracting RES+70','exact source2 target and timeMode0','dubow CircleCollider radius2 supplement']},
            {'owner':'next content author','variants':['dumage','dushld','duphlx'],'dependencies':['source-specific stats/Spine/projectile','refracting','duphlx DEF200 aura']},
            {'owner':'next coupled content author','variants':['duholy','dushdo'],'dependencies':['duholy source aura/toggle peer','Flame ownership','dushdo invisibility/trait timing']},
            {'owner':'generic + content authors','variants':['duspfr'],'dependencies':['EP contract','Flame10.6','before-zero deadboom3s and five parallel child actions']},
            {'owner':'generic + predefined content authors','variants':['trap_043_dupilr','trap_045_dublst','trap_044_duruin'],'dependencies':['record-index registration','directional collapse','terrain token/repath','demolition immediate source trigger']},
            {'owner':'later content authors','variants':['durokt','dugago'],'dependencies':['exact flight/ground states and recover/stone passives']},
            {'owner':'Boss source author','variants':['mandra'],'dependencies':['four exact remapped modes','ray/stone/rebirth','distinct skill vs talent BB prefixes','native Level branches null vs skill branch names; actual SpawnTokenOnTile helper']}],
        'admission':'9-18 requires all its six native variants plus pillar/demolition/ruin and EP/deadboom consumers; no partial whole claim.'})
    pins = [{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(BASE.glob('*.json'))]
    helpers = [{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(Path(__file__).parent.glob('*.py'))]
    write('source.freeze.v1.json', {'schema':'ark-sim/c9-source-freeze/v1','fixed_commit':FIXED,
        'files':pins,'helpers':helpers,'runtime_changed':False,'whole_stage_verified':False,
        'claims':'Offline source preparation and explicit replaceable interface policies only; no compiler/gameplay/client approval.'})
    print(json.dumps({'freeze_sha256':sha(BASE/'source.freeze.v1.json'),'file_count':len(pins),'helper_count':len(helpers)}))

if __name__ == '__main__':
    main()
