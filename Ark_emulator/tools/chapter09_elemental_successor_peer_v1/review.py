"""Independent typed source review of selected ally receiver mounting."""
import sys,json,copy,hashlib,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter10_stage_source_peer_v1.source_preflight import exact
OUT=ROOT/'validation/campaign/chapter09_elemental_successor_peer_v1';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_bytes())
def main():
    roster_path=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json';recipe_path=ROOT/'packages/campaign/common_elemental_receivers/recipe.ally.current.v1.json';roster=load(roster_path);recipe=load(recipe_path)
    actors={d['id'] for d in roster['definitions'] if d['kind']=='entity'};assert len(actors)==15
    files=[Path(__file__),roster_path,recipe_path,ROOT/'tools/chapter09_elemental_successor_v1/build.py',ROOT/'tools/chapter09_elemental_successor_v1/providers.py',ROOT/'tools/campaign_elemental_receivers_v1/build.py'];proofs=[]
    for stage,suffix in [('09-16','918'),('09-17','919')]:
        receipt_path=ROOT/f'validation/campaign/chapter09_elemental_successor_v1/source.{suffix}.v1.json';receipt=load(receipt_path);path=Path(receipt['output']);new=load(path);binding=new['manifest']['metadata']['elemental_successor_binding'];parent_path=Path(binding['parent']);old=load(parent_path);files.extend([receipt_path,path,parent_path]);assert sha(path)==receipt['output_sha256'] and sha(parent_path)==binding['parent_sha256']
        olddefs={d['id']:d for d in old['definitions']};defs={d['id']:d for d in new['definitions']};selected=set(binding['selected_receivers']);assert selected==actors
        owned={a for id in actors for a in olddefs[id]['components'].get('abilities',[])};assert set(binding['owned_abilities'])==owned
        foreign_actors=[d for d in olddefs.values() if d['kind']=='entity' and d['id'] not in actors]
        foreign_owned={a for e in foreign_actors for a in e['components'].get('abilities',[])};assert not (foreign_owned & owned),'Shared ability ownership needs explicit replacement policy'
        exact(new['scenarioDraft'],old['scenarioDraft']);changes=binding['explicit_original_changes'];assert set(changes)<=actors|owned and len(changes)==32 and len(set(defs)-set(olddefs))==20
        preserved=[];spchains=[];skills=[]
        for id,original in olddefs.items():
            expected=copy.deepcopy(original)
            if id in actors:
                components=expected['components'];assert 'elemental' not in components
                components['elemental']=copy.deepcopy(recipe['receiver_template']);spec=components.get('resources',{}).get('sp')
                if spec is not None:
                    old_rule=spec.get('recovery_freeze_rule') or spec.get('rules',{}).get('resource.recovery_freeze');rid='rule/campaign/elemental_receivers/freeze/'+id.replace('/','_');spec['recovery_freeze_rule']=rid
                    rule=defs[rid];assert rule['parameters']=={'buff':'buff/campaign/elemental_receivers/dark',**({'base_rule':old_rule} if old_rule else {})} and rule['dependencies']==([old_rule] if old_rule else [])
                    assert rule['implementation']=={'type':'provider','provider':'reference.campaign.elemental.freeze'};spchains.append({'entity':id,'original_rule':old_rule,'new_rule':rid})
            elif original['kind']=='ability' and id in owned:
                activation=expected.get('activation',{})
                if activation.get('mode')=='manual' or activation.get('parameters',{}).get('replace_attack'):
                    activation['forbidden_source_flags']=list(dict.fromkeys([*activation.get('forbidden_source_flags',[]),24]));skills.append(id)
            else:preserved.append(id)
            exact(expected,defs[id],stage+'.'+id)
            if id in changes:exact(original,changes[id]['before']);exact(defs[id],changes[id]['after'])
        restored=copy.deepcopy(new);restored['definitions']=[copy.deepcopy(changes[d['id']]['before']) if d['id'] in changes else d for d in new['definitions'] if d['id'] in olddefs];restored['manifest']['metadata']['required_runtime']=old['manifest']['metadata']['required_runtime'];del restored['manifest']['metadata']['elemental_successor_binding'];exact(restored,old)
        for path_,value in [*old['manifest']['metadata']['source_locks'].items(),*binding['source_locks'].items()]:assert sha(Path(path_))==value,path_;files.append(Path(path_))
        # Every present final Buff must have current native/projected flags.
        flags=defs['rule/campaign/elemental_receivers/eligible']['parameters']['buff_flags']
        for d in defs.values():
            if d['kind']=='buff':exact(flags[d['id']],{'flags':d.get('selection_flags',{}).get('abnormal_flags',[]),'immunes':d.get('selection_flags',{}).get('abnormal_immunes',[])},d['id']+'.flags')
        excluded=[{'entity':e['id'],'side':e['components'].get('selection_state',{}).get('side'),'tags':e.get('tags',[]),'unchanged':True,'reason':'Outside exact fixed12+3summon reference receiver scope; preserve source mechanism/enemy ownership. This is not a universal claim about all side0 device EP susceptibility.'} for e in foreign_actors]
        proofs.append({'stage':stage,'package_sha256':sha(path),'parent_sha256':sha(parent_path),'all_scenario_fields_type_exact_equal':True,'explicit_original_changes':32,'new_definitions':20,'unrelated_definition_count_unchanged':len(preserved),'selected_fixed15':sorted(actors),'owned_skills_gated':skills,'SP_original_freeze_compositions':spchains,'excluded_mechanisms_and_enemies':excluded,'restored_parent_package_type_exact_equal':True,'receipt_program':receipt['program']})
    files=list(dict.fromkeys(files));before={str(p):sha(p) for p in files}
    from tools.campaign_elemental_receivers_v1.build import frozen_recovery
    # Only inspect source code for base delegation. Do not run actor resources.
    import inspect
    assert "context.calculate('resource.recovery_freeze', inputs, rule_id=parameters['base_rule'])" in inspect.getsource(frozen_recovery)
    after={str(p):sha(p) for p in files};assert before==after
    report={'schema':'ark-sim/chapter9-ally-elemental-successor-source-review/v1','source_input_approved':True,'source_before':before,'source_after':after,'source_equal':True,'stages':proofs,'reviewed_runtime_declaration':'94d2f5cfcc42f8845c6cb23643f1910aa94a78115a60d83813d0738df6db8c63','simulation_started':False,'core_approved':False,'model_approved':False,'whole_stage_approved':False,'client_verified':False,'scope':'Strict original scene/all defs comparison and explicit ally receiver/SP/owned skill changes only. Active prefix/whole results remain Root separate actual gates.'}
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'source.review.v1.json';assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'source_input_approved':True,'report_sha256':sha(path),'stages':[(p['stage'],p['explicit_original_changes'],p['new_definitions']) for p in proofs]}))
if __name__=='__main__':main()
