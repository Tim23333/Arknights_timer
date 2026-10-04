"""Bind fresh marker gate to current admitted draft/runtime; retain old known3992 failure scope."""
from pathlib import Path
HERE=Path(__file__).parent
s=(HERE/'verify_uoffcr_marker_gate_v1.py').read_text().replace('campaign_area_projection_v2_candidate','campaign_behavior_restart_clock_v2_candidate').replace('uoffcr.module.v1.json','uoffcr.module.v3.json').replace('from tools.chapter08_ranged.policies_v1 import providers','from tools.chapter08_stage_join.runner_providers_v1 import providers').replace("OUT=ROOT/'packages/campaign/chapter08_consumers/special/uoffcr_marker_gate_v1'","OUT=ROOT/'packages/campaign/chapter08_consumers/special/uoffcr_marker_gate_v2'")
s=s.replace("sha(OUT/'source.audit.json')","sha(OUT.parent/'uoffcr_marker_gate_v1/source.audit.json')")
s=s.replace("before=sha(MODULE);rows=[];", "draft=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v3.json';overlay=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v3.life99999.v1.json';assert sha(draft)=='8a5debd1963964e9a3f59aa19cd91625ebe9f7108676016151c2030c98786efa';assert sha(overlay)=='f48318f619e63e391d7ee40b111becb1a40c54e14db432923d4d72664d88505f';OUT.mkdir(exist_ok=True);before=sha(MODULE);rows=[];")
s=s.replace("'current_fixed12_roster':", "'current_draft_identity':{'native':sha(draft),'life_overlay':sha(overlay),'runner_providers':sha(ROOT/'tools/chapter08_stage_join/runner_providers_v1.py')},'current_fixed12_roster':")
(HERE/'verify_uoffcr_marker_gate_v2.py').write_text(s,encoding='utf-8',newline='')
