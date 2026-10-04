"""Guarded independent M72 actual-source/model verification."""
from pathlib import Path
import contextlib,hashlib,importlib.util,io,json,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m72_no_source_damage_candidate'
OUT=ROOT/'validation/campaign/m72_no_source_damage'
ENV=ROOT/'packages/campaign/chapter04_environment/source.reference.json'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
    return {group:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern))
        if p.is_file() and '__pycache__' not in p.parts}
        for group,folder,pattern in [('m72_source',RUNTIME/'ark_sim','*.py'),
            ('m68_source',ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate/ark_sim','*.py'),
            ('m71_frozen',ROOT.parent/'unpack_work/campaign_m71_event_storage_candidate/ark_sim','*.py'),
            ('m72_tools',ROOT/'tools/candidates/m72_no_source_damage','*'),
            ('m72_experiments',ROOT/'tools/experiments/m72_no_source_damage','*.py')]}

def core(m):return hashlib.sha256(json.dumps(m,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # The tool directory contains files only; exclude cache directories explicitly.
    spec=importlib.util.spec_from_file_location('m72_builder',ROOT/'tools/candidates/m72_no_source_damage/build.py')
    b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    before=guard();catalog={str(p):sha(p) for p in [ENV,ROOT/'packages/custom/custom_guard.json',
        ROOT/'packages/ark_content/level_main_00_01.json',ROOT/'scenarios/level_main_00_01/commands.json',
        ROOT/'tools/campaign_ordered_checkpoint.py',RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json']}
    assert sha(ENV)=='148a5a8648801f8c7eee655d5c0daa1f4f7469cefe3abd2d304dcdc33a121dc8'
    assert core(before['m68_source'])=='1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'
    assert core(before['m71_frozen'])=='15517b90969c61b15340929687092401b4a807b6a3f66d0d2135e780568c04aa'
    bootstrap="import sys,pytest;sys.path.insert(0,"+repr(str(RUNTIME))+");sys.exit(pytest.main(['tools/experiments/m72_no_source_damage/test_no_source.py','tests_v2/test_kernel.py','tests_v2/test_damage_hooks_random.py','tests_v2/test_event_resources.py','tests_v2/test_scenario_effects.py','tests_v2/test_qualified_area_visibility_integration.py','tests_v2/test_replay.py','-q']))"
    run=subprocess.run([sys.executable,'-c',bootstrap],cwd=ROOT,capture_output=True,text=True)
    (OUT/'tests.log').write_text(run.stdout+run.stderr,encoding='utf8')
    assert run.returncode==0,run.stdout+run.stderr
    noopt=subprocess.run([sys.executable,str(Path(__file__).with_name('compare_parent.py'))],cwd=ROOT,capture_output=True,text=True)
    (OUT/'no-opt.log').write_text(noopt.stdout+noopt.stderr,encoding='utf8')
    assert noopt.returncode==0,noopt.stdout+noopt.stderr
    with tempfile.TemporaryDirectory(prefix='m72_build_reproduce_',dir=RUNTIME.parent) as temporary:
        b.OUT=Path(temporary)/'candidate'
        with contextlib.redirect_stdout(io.StringIO()):b.main()
        reproduction=core(before['m72_source'])==b.core(b.OUT)
        assert reproduction,'Build source differs from actual candidate'
    after=guard();catalog_after={path:sha(Path(path)) for path in catalog}
    assert before==after and catalog==catalog_after,'Source/tools/catalog changed during validation'
    def nodes(value):
        if isinstance(value,dict):
            if value.get('$type','').endswith('+NoSourceDamage'):yield value
            for child in value.values():yield from nodes(child)
        elif isinstance(value,list):
            for child in value:yield from nodes(child)
        elif isinstance(value,str) and '+NoSourceDamage' in value:
            try: decoded=json.loads(value)
            except ValueError:return
            yield from nodes(decoded)
    env_data=json.loads(ENV.read_text(encoding='utf8'))
    source_nodes=list(nodes(env_data))
    assert len(source_nodes)==1,'Expected exact serialized-state NoSourceDamage node'
    assert all(source_nodes[0][k]==v for k,v in {
        '_damageType':'PURE','_attackType':'NONE','_ignoreForSp':False,
        '_damageWithoutModify':False,'_isEnvDamage':False,'_isUndeadable':False,
        '_instantKillLikeDamage':False,'_isNotChangeableValue':False}.items())
    components=[];typed_rows=[]
    for component_id,component in env_data['prefabs']['tile_volcano']['components'].items():
        raw=component['raw']
        if not isinstance(raw.get('_actions'),dict):continue
        text=raw['_actions']['SerializedState']
        decoded=json.loads(text)
        if not isinstance(decoded,list):continue
        selected=[(index,node) for index,node in enumerate(decoded) if node.get('$type','').endswith('+NoSourceDamage')]
        if not selected:continue
        base='/prefabs/tile_volcano/components/'+component_id+'/raw'
        assert type(raw['_injectEnvDmgFlagToBlackboard']) is int and raw['_injectEnvDmgFlagToBlackboard']==1
        components.append({'component_path':base,'component_path_id':component_id,
            'gameobject_path_id':component['gameobject_path_id'],'script_path_id':component['script_path_id'],
            'serialized_state_path':base+'/_actions/SerializedState',
            'serialized_state_sha256':hashlib.sha256(text.encode('utf8')).hexdigest(),
            'decoded_nodes':decoded,'inject_env_dmg_flag_raw':raw['_injectEnvDmgFlagToBlackboard']})
        index,node=selected[0]
        for source_key,target_key,target_value,policy in [
            ('_damageType','damage_type','true','explicit PURE-to-V2 true damage enum mapping'),
            ('_attackType','attack_type',node['_attackType'],'same enum value'),
            ('_ignoreForSp','ignore_for_sp',node['_ignoreForSp'],'same boolean value'),
            ('_damageWithoutModify','damage_without_modify',node['_damageWithoutModify'],'same boolean value'),
            ('_isEnvDamage','node_is_env_damage',node['_isEnvDamage'],'same raw node boolean; not inferred from injection')]:
            typed_rows.append({'source_path':base+'/_actions/SerializedState::decoded/'+str(index)+'/'+source_key,
                'raw_value':node[source_key],'raw_type':type(node[source_key]).__name__,
                'request_field':target_key,'request_value':target_value,'request_type':type(target_value).__name__,'policy':policy})
        typed_rows.append({'source_path':base+'/_injectEnvDmgFlagToBlackboard','raw_value':1,'raw_type':'int',
            'request_field':'env_blackboard_injected','request_value':True,'request_type':'bool',
            'policy':'explicit serialized 0/1 switch conversion; independent of node_is_env_damage'})
    assert len(components)==1
    stage_tiles=env_data['stage_tile_operands']['level_main_04-09']
    assert len(stage_tiles)==8
    for index,tile in enumerate(stage_tiles):
        values={row['key']:row['value'] for row in tile['blackboard']}
        assert values['damage']==700 and values['cd_min']==13 and values['cd_max']==19
        typed_rows.append({'source_path':'/stage_tile_operands/level_main_04-09/'+str(index)+'/blackboard',
            'raw_value':values,'raw_type':'dict','request_field':'fixed_amount','request_value':values['damage'],
            'request_type':type(values['damage']).__name__,'policy':'NoSourceDamage._damageKey damage resolves actual stage BB; timing operands belong to M62'})
    typed_rows.append({'source_path':None,'request_field':'environmental','request_value':True,
        'request_type':'bool','policy':'explicit reference ENV projection selected by M62; not a claim that raw node_is_env_damage is true'})
    report={'passed':True,'core':core(after['m72_source']),'parent_core':core(after['m68_source']),
        'source_environment_sha256':sha(ENV),'raw_no_source_nodes':source_nodes,
        'decoded_components':components,'source_request_typed_rows':typed_rows,
        'tests_summary':run.stdout.strip().splitlines()[-1], 'build_reproduction_all_python_bytes_equal':reproduction,
        'no_opt_comparison':'no_opt_comparison.json','start_manifest':before,'end_manifest':after,
        'catalog_before':catalog,'catalog_after':catalog_after,'source_tools_catalog_start_end_equal':True,
        'scope':'Generic source-independent settlement and small model/source regressions; no periodic-field or fullstage claim',
        'limitations':['M62 periodic membership/trigger/runtime remains separate Root integration',
            'M61 staged rebirth integration is separate; standard revive tested, no immediate forced kill in no-source settlement',
            'Death reaction queue remains existing engine semantics; no broad actor-path None relaxation',
            'Current explicit protocol requires PURE true, attack_type NONE, damage_without_modify False']}
    with (OUT/'verification_final.json').open('x',encoding='utf8') as file:
        json.dump(report,file,ensure_ascii=False,indent=2);file.write('\n')
    print(json.dumps({'passed':True,'core':report['core'],'tests':report['tests_summary'],'source_nodes':len(source_nodes)}))

if __name__=='__main__':main()
