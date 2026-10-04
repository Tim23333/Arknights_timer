"""Independent bounded 0fb source-consumer review, explicitly blocked on gating."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT.parent / "unpack_work/campaign_m12_projection_candidate"))
from ark_sim import Compiler
from ark_sim.contracts import thaw


def read(p): return json.loads(p.read_bytes())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(value): return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def static_keys(node):
    if isinstance(node, ast.Dict):
        result = []
        for key, value in zip(node.keys, node.values):
            if key is None: result += static_keys(value)
            else: result.append(ast.literal_eval(key))
        return result
    if isinstance(node, ast.DictComp):
        gen = node.generators[0]; assert len(node.generators)==1 and not gen.ifs
        values = ast.literal_eval(gen.iter)
        def expr(value, bound):
            if isinstance(value, ast.Constant): return value.value
            if isinstance(value, ast.Name): return bound[value.id]
            if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add): return expr(value.left,bound)+expr(value.right,bound)
            raise ValueError("nonliteral finite key")
        return [expr(node.key,{gen.target.id:v}) for v in values]
    raise ValueError("unreviewed CASES syntax")


def run():
    content = ROOT / "packages/campaign/mainline_models/level_main_00-10.m12_projection.json"
    draftpath = ROOT / "packages/mainline/main_00-10.json"; auditpath = ROOT / "packages/campaign/conversion_drafts/main_00-10.audit.json"
    base, draft, audit = read(content), read(draftpath), read(auditpath)
    assert sha(content) == "0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4"
    for k in set(base)-{"manifest","scenarioDraft","status"}: assert base[k] == draft[k]
    a,b=deepcopy(base["scenarioDraft"]),deepcopy(draft["scenarioDraft"]);a.pop("metadata");b.pop("metadata");assert a==b
    source_locks = []
    for row in audit["source_locks"]:
        p=ROOT/row["path"]; assert sha(p)==row["sha256"];source_locks.append({"path":row["path"],"sha256":sha(p)})
    program=Compiler().compile(base);definitions={k:thaw(v) for k,v in program.definitions.items()}
    normalized=read(ROOT/"packages/campaign/operators.normalized.json")
    mapping={"maxHp":"max_hp","atk":"atk","def":"def","magicResistance":"mres","baseAttackTime":"attack_interval","moveSpeed":"move_speed","blockCnt":"block_count","cost":"deploy_cost","respawnTime":"redeploy_time","massLevel":"mass_level"}
    unit_results=[]
    for record in normalized["operators"]:
        unit=definitions["unit/"+record["character_id"]];component=unit["components"];stats=record["stats"]["model_stats"]
        assert all(component["attributes"]["base"][v]==stats[k] for k,v in mapping.items())
        assert component["attributes"]["base"]["attack_speed_ratio"]==stats["attackSpeed"]/100
        selected=unit["metadata"]["selected_skill_ability"];assert selected in component["abilities"]
        assert definitions[selected]["metadata"]["native_skill_id"]==record["selected_skill"]["skill_id"]
        assert unit["metadata"]["config"]==record["config"]
        assert component["resources"]["sp"]["initial"]==record["selected_skill"]["level"]["spData"]["initSp"]
        assert component["resources"]["sp"]["capacity"]==record["selected_skill"]["level"]["spData"]["spCost"]
        unit_results.append({"character_id":record["character_id"],"selected_ability":selected,"stats_config_owned_SP_checked":True,
            "initial_talents":component.get("buffs",{}).get("initial",[])})
    for closure in audit["operator_definition_closures"]:
        for item in closure["reachable_definition_identities"]:assert ident(definitions[item["id"]])==item["sha256"]
    node_results=[]
    for row in audit["primary_suite_node_source_mapping"]:
        test_path=ROOT/row["test_node_id"].split("::")[0];helper_path=ROOT/row["helper_path"]
        assert sha(test_path)==row["test_source_sha256"] and sha(helper_path)==row["helper_sha256"]
        test_tree=ast.parse(test_path.read_text(encoding='utf8'));helper_tree=ast.parse(helper_path.read_text(encoding='utf8'))
        function=row["test_node_id"].split("::")[1].split("[")[0]
        assert any(isinstance(n,ast.FunctionDef) and n.name==function for n in test_tree.body)
        if '[' in row['test_node_id']:
            assignment=next(n for n in helper_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CASES' for t in n.targets))
            keys = static_keys(assignment.value)
            for n in helper_tree.body:
                if isinstance(n,ast.Assign):
                    for target in n.targets:
                        if isinstance(target,ast.Subscript) and isinstance(target.value,ast.Name) and target.value.id=='CASES':
                            keys.append(ast.literal_eval(target.slice))
            assert row["case"] in keys
            assert any(isinstance(n,ast.ImportFrom) and n.module=="tools."+helper_path.stem and any(x.name=="CASES" for x in n.names) for n in test_tree.body)
        node_results.append({"node":row["test_node_id"],"source_sha256":sha(test_path),"helper_sha256":sha(helper_path),"finite_AST_case_and_test_binding":True})
    assert len(node_results)==59 and len({r['node'] for r in node_results})==59
    provenance=read(ROOT/"validation/campaign/m12_primary_launch_provenance_20261002.json")
    selected_records=[provenance['launch'],provenance['launch_response'],provenance['terminal_poll']['call'],provenance['terminal_poll']['response']]
    wanted={r['line_number']:r for r in selected_records};checked=[]
    with Path(provenance['source_transcript']).open('rb') as stream:
        for line_index,line in enumerate(stream,1):
            if line_index not in wanted:continue
            record=json.loads(line);expected=wanted[line_index]
            assert record==expected['record']
            assert hashlib.sha256(line).hexdigest()==expected['record_sha256']
            checked.append(line_index)
    assert len(checked)==4
    script=provenance['launch']['record']['payload']['input']
    assert '$env:CAMPAIGN_MECHANISM_PACKAGE=' in script and '$env:CAMPAIGN_SUMMON_PACKAGE=$env:CAMPAIGN_MECHANISM_PACKAGE' in script
    assert 'level_main_00-10.m12_projection.json' in script and '$env:ARKSIM_M10_REVIEW_ROOT=(Get-Location).Path' in script
    affected=[r for r in audit['field_audit'] if any(key in r['native_pointer'] for key in ('maxTimeWaitingForNextWave','managedByScheduler','dontBlockWave'))]
    assert affected and all(r['classification']=='consumed_math' for r in affected)
    assert 'timeline' not in base['scenarioDraft'] and len(base['scenarioDraft']['waves'])==35
    return {'schema':'ark-sim/bounded-source-consumer-peer/v1','status':'blocked_current_0fb_complete_conversion',
        'subject_model_content_sha256':sha(content),'implementation_sha256':'bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11',
        'draft_sha256':sha(draftpath),'audit_sha256':sha(auditpath),'source_locks_checked':source_locks,'operator_consumers':unit_results,
        'closure_identity_rows_checked':sum(len(r['reachable_definition_identities']) for r in audit['operator_definition_closures']),
        'canonical_nodes':node_results,'launch_actual_transcript_lines_checked':checked,'launch_environment_assignment_seen':True,
        'environment_scope':'literal actual launch chain verified; not in-process instrumentation',
        'actual_source_consumer_gap':{'id':'native_managed_wave_gate_flattened','affected_records':affected,
            'actual_consumer':'flat fixed absolute waves; no Timeline membership/max_wait','classification':'math/source-consumer gap',
            'required_fix':'new M14 Timeline content + fresh fullstage witnesses; do not relabel old win'},
        'bounded_checks':{'unit_attributes_and_growth':'model_stats/config mapping passed; client interpolation/calibration pending',
            'selected_skills_and_talents':'selected owned/SP/initial talent and closure identity checked; execution scope needs required case evidence',
            'native_enemy_dependencies':'raw value scope may cite independent root 270Unity/2526JSON review; source lock independently checked',
            'map_path_and_canonical_log':'blocked: native scheduler gate not consumed by 0fb',
            'ui_kernel_formula_separation':'opaque UI profile; logical zero-time model, native callbacks pending'},
        'formal_approval':False,'external_receipt_issued':False}


if __name__ == '__main__':
    value=run();p=ROOT/'validation/campaign/first_model_source_consumer_peer_gap.json';p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':value['status'],'nodes':len(value['canonical_nodes']),'locks':len(value['source_locks_checked']),'units':len(value['operator_consumers'])}))
