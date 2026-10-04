"""New 1-11 wrapper: actual predefine registered at start, activated by key."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_chapter01_stage_models import build as stage_build, encoded, sha, top_position

INPUT = ROOT/"packages/campaign/chapter01_stage_models/level_main_01-11.partial.json"
INPUT_SHA = "7a40950d378bc6668563d6b9a6c5656f3903cf5197543fc77d89e8d3f986985d"
SOURCE = ROOT/"packages/campaign/chapter01_predefines/native.reference.json"
SOURCE_SHA = "15eb6edf057af42e1c03acf441cc44852f1a3b4aefd511dd23428fcead1413e6"
RANGE = ROOT.parent/"unpack_work/campaign_tables/range_table.reference_56a.json"
RANGE_SHA = "a98344d688a8933c4dd7ddaae3cb76c4347295359a18b60b918042cc2542d9d9"
RUNTIME = ROOT.parent/"unpack_work/campaign_m20_dormant_candidate"
CORE = "db6134da42647f1691f8b6fb5318fa8bbbcc455b26b1dc59841d6c1eba95bdcc"
OUT = ROOT/"packages/campaign/chapter01_stage_models/m20/level_main_01-11.dormant.partial.json"


def build():
    if sha(INPUT) != INPUT_SHA or sha(SOURCE) != SOURCE_SHA or sha(RANGE) != RANGE_SHA:
        raise ValueError("frozen stage/NPC/official range source drift")
    p = json.loads(INPUT.read_bytes())
    if p != stage_build("level_main_01-11"): raise ValueError("frozen parent stage composition drift")
    reference = json.loads(SOURCE.read_bytes()); prefab = reference['prefab']
    asset = ROOT.parent/prefab['source']['path']
    if sha(asset) != prefab['source']['sha256']: raise ValueError('actual Character asset drift')
    chars = [(pid, c) for pid, c in prefab['components'].items() if c['native_class'] == 'Character']
    if len(chars) != 1: raise ValueError('ambiguous native Character component')
    pid, character = chars[0]
    import UnityPy
    env = UnityPy.load(str(asset)); objects = [obj for obj in env.objects if obj.path_id == int(pid)]
    if len(objects) != 1 or objects[0].read_typetree() != character['raw']:
        raise ValueError('fresh Character typetree differs from source reference')
    fields = character['raw']; occupy = fields['_occupiedRemainingCharacterCnt']
    if type(occupy) is not int or occupy != 1 or fields['_buildCondition']['buildableType'] != 2:
        raise ValueError('predefined Character capacity/build model changed')
    if json.loads(RANGE.read_bytes())['3-1'] != reference['native_range']:
        raise ValueError('official source range differs from old offline reference')
    scene = p['scenarioDraft']; meta = p['manifest']['metadata']
    insts = meta['native_predefines']['characterInsts']
    if len(insts) != 1 or not insts[0]['hidden'] or insts[0]['alias'] is not None:
        raise ValueError('expected one actual hidden aliasNone Character')
    inst = insts[0]; key = inst['inst']['characterKey']; npc_id = 'unit/ch1_predefined_adnach_e0_l20'
    npc = next(e for e in p['entities'] if e['id'] == npc_id)
    if reference['selected_skill_level']['spData']['spType'] != 'INCREASE_WITH_TIME' or reference['raw_character']['profession'] != 'SNIPER':
        raise ValueError('source NPC profession or SP type changed')
    npc['tags'] = list(dict.fromkeys([*npc['tags'], 'time_sp', 'profession:SNIPER', 'profession_SNIPER']))
    attrs = npc['components']['attributes']
    attrs['base']['sp_recovery_rate'] = reference['selected_skill_level']['spData']['increment']
    attrs['layers'] = ['flat', 'direct_ratio', 'final_ratio', 'sluggish', 'fragility', 'sp_recovery']
    npc.setdefault('rules', {})['attributes.effective'] = 'rule/support_temporal'
    npc['components']['resources']['sp']['recovery_rule'] = 'rule/support_time_sp'
    npc['components']['deployable'] = {'policy': 'policy/ark_ground_deploy', 'terrain': 'high',
        'base_cost': npc['components']['attributes']['base']['deploy_cost'], 'capacity': occupy,
        'refund_ratio': fields['_withdrawCostRecoverRatio'],
        'cooldown_seconds': npc['components']['attributes']['base']['redeploy_time'],
        'parameters': {'advanced_build_mask': fields['_buildCondition']['advancedBuildableMask'],
            'refund_cap_raw_ratio': fields['_maxWithdrawCostRatioOfRawCost']}}
    npc.setdefault('metadata', {})['predefined_activation_profile'] = {
        'registration': 'living inactive instance at stage start; aliasNone',
        'initialization': 'resources/buffs/deck/behavior/lifetime deferred to activation',
        'payment': 'preplaced free profile; paid_cost0; native predefined refund basis unknown',
        'capacity': 'native occupiedRemainingCharacterCnt consumed only while active',
        'time_sp': 'source time recovery joins shared Ptilopsis aura by actual SP type and profession',
        'native_game_wall_clock_and_hidden_SP': 'client_pending'}
    scene['initialEntities'].append({'definition': npc_id, 'registration_key': key, 'active': False,
        'position': top_position(inst['position'], scene['map']['rows']), 'facing': inst['direction'].lower(), 'deployed': True})
    activated = 0
    for control in p['controls']:
        if control.get('metadata', {}).get('native_action', {}).get('actionType') == 'ACTIVATE_PREDEFINED':
            source_action = control['metadata']['native_action']
            if source_action['key'] != key or source_action['count'] != 1: raise ValueError('activation source key/count changed')
            replacements = 0
            for step in control['steps']:
                for index, effect in enumerate(step.get('effects', [])):
                    if effect.get('op') == 'spawn':
                        if effect['definition'] != npc_id: raise ValueError('wrong source NPC activation')
                        step['effects'][index] = {'op': 'activate_predefined', 'target': 'battle', 'parameters': {'key': key}}
                        replacements += 1
                    elif effect.get('event') == 'chapter01.predefined.model_creation_requested':
                        effect['event'] = 'chapter01.predefined.model_activation_requested'
                        effect['payload'].update(policy='registered_dormant_then_activate_same_instance_v1', native_dormant_registry_converted=True,
                            native_dormant_registry_body_verified=False)
            if replacements != 1: raise ValueError('exact one native activation effect required')
            control['metadata'].update(profile='registered_dormant_then_activate_same_instance_v1', native_UI_or_dormant_registry_completed=False,
                declared_dormant_model_completed=True)
            activated += 1
    if activated != 1: raise ValueError('source activation conservation failed')
    meta['pending_model_gaps'] = [gap for gap in meta['pending_model_gaps'] if gap != 'predefined_hidden_dormant_registry_activation_and_SP_clock']
    meta.update(required_runtime=CORE, builder_sha256=sha(Path(__file__)), parent_input_sha256=INPUT_SHA)
    meta['source_locks'].update({INPUT.relative_to(ROOT).as_posix(): INPUT_SHA, SOURCE.relative_to(ROOT).as_posix(): SOURCE_SHA,
        '../unpack_work/campaign_tables/range_table.reference_56a.json': RANGE_SHA,
        '../'+prefab['source']['path']: prefab['source']['sha256']})
    meta['model_profiles']['NPC'] = deepcopy(npc['metadata']['predefined_activation_profile'])
    p['manifest']['id'] = 'package/campaign/chapter01_stage/level_main_01-11/m20'
    scene['id'] = 'scenario/campaign/chapter01/level_main_01-11/m20'
    return p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    sys.path.insert(0, str(RUNTIME))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent != RUNTIME/'ark_sim' or implementation_digest() != CORE:
        raise RuntimeError('wrong dormant candidate runtime')
    p = build(); program = Compiler().compile(p); OUT.parent.mkdir(parents=True, exist_ok=True)
    if args.check:
        if OUT.read_bytes() != encoded(p): raise ValueError('dormant composition drift')
    else: OUT.write_bytes(encoded(p))
    print(json.dumps({'definitions': len(program.definitions), 'implementation': CORE, 'package_sha256': sha(OUT), 'whole_stage': False}))
