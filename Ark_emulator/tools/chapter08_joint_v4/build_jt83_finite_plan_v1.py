"""Finite public player workload; late withdrawals prevent healing stalemate."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v4.json'
PRIOR=PARENT.with_name('level_main_08-17.native_draft.v4.life99999.v1.json')
COMMANDS=ROOT/'scenarios/campaign/chapter08/level_main_08-17/public_plan_v3_finite/commands.json'
OUT=PARENT.with_name('level_main_08-17.native_draft.v4.life99999.finite_v2.json')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    from tools.campaign_runthrough_progress_v5 import validate_native_overlay
    assert sha(PARENT)=='fdfa0bca0f6034602d1f69630b8727db74c864c226e4de3c17ea3150fae1860a'
    p=json.loads(PRIOR.read_bytes())
    original=ROOT/'scenarios/campaign/chapter08/level_main_08-17/public_plan_v2/commands.json'
    actions=json.loads(original.read_bytes())
    aliases=[row['alias'] for row in actions if row['action']=='deploy'];assert len(aliases)==12
    for offset,alias in enumerate(aliases):
        actions.append({'at':9000+offset,'action':'withdraw','source':alias})
    actions.sort(key=lambda action:action['at'])
    assert not COMMANDS.exists() and not OUT.exists()
    COMMANDS.parent.mkdir(parents=True,exist_ok=True)
    COMMANDS.write_bytes((json.dumps(actions,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    p['scenarioDraft']['metadata']['runthrough_profile']['public_commands_sha256']=sha(COMMANDS)
    validate_native_overlay(p,json.loads(PARENT.read_bytes()),COMMANDS)
    assert p['definitions']==json.loads(PARENT.read_bytes())['definitions']
    OUT.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    receipt={'native_parent_sha':sha(PARENT),'overlay_sha':sha(OUT),'commands_sha':sha(COMMANDS),
             'original_command_count':28,'public_tail_withdrawals':12,'total_commands':40,
             'final_withdrawal_at':9011,'source_stats_and_scene_unchanged':True,
             'purpose':'Declared public finite testing workload: end player healing combat after300seconds, then simulate all remaining original waves and lifecycles',
             'command_rejections_recorded':True,'whole_stage_executed':False,
             'old_full_run_not_relabelled':True,'client_verified':False}
    path=ROOT/'validation/campaign/campaign_foundation_v5/jt83_finite_public_plan_v1.json'
    path.write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps(receipt))


if __name__=='__main__':
    import sys;sys.path.insert(0,str(ROOT));build()
