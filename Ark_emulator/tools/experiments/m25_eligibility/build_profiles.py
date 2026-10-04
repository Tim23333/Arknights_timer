"""Offline exact native selector fields -> declared M25 qualification profiles."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m25_eligibility_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from test_eligibility import fixture,DEFAULTS
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
OUT=ROOT/'packages/campaign/selector_eligibility/m25.source_profiles.json'
def build():
    import UnityPy
    audit_path=ROOT/'validation/campaign/advanced_selector_source_audit.json';audit=json.loads(audit_path.read_bytes());assert audit['passed'];cache={};p=fixture();p['selectors']=[];records=[]
    for row in audit['actual_selectors']:
        source=row['source'];path=ROOT.parent/source['path'];assert sha(path)==source['sha256']
        if path not in cache:cache[path]={o.path_id:o for o in UnityPy.load(str(path)).objects}
        assert cache[path][row['actual_component_path_id']].read_typetree()==row['raw']
        id='selector/m25/native/'+str(row['actual_component_path_id']);spec={'rule':'rule/eligibility','parameters':{'source_configuration':row['raw'],'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':DEFAULTS}}
        p['selectors'].append({'id':id,'kind':'selector','region':{'type':'all'},'filters':[{'state':'alive'}],'eligibility':spec,'metadata':{'source':source,'actual_component_path_id':row['actual_component_path_id'],'native_class':row['actual_native_class'],'native_owner':row['owner'],'geometry_scope':'all region qualification probe only; native range/order not claimed'}})
        records.append({'source':source,'native_owner':row['owner'],'component':row['actual_component_path_id'],'selector_definition':id})
    for entity in p['entities']:entity['dependencies']=[s['id'] for s in p['selectors']]
    mother_path=ROOT/'packages/campaign/chapter01_sources/native.reference.json';mother=json.loads(mother_path.read_bytes());binding_evidence=[]
    for owner in ('enemy_1028_mocock','enemy_1028_mocock_2','enemy_1504_cqbw'):
        comps=mother['enemies'][owner]['prefab']['components'];record=mother['enemies'][owner]['prefab']['source'];asset=ROOT.parent/record['path'];assert sha(asset)==record['sha256'];objects=cache[asset]
        for mode_id,item in comps.items():
            if item['native_class']!='UnitMode':continue
            mode=objects[int(mode_id)].read_typetree();assert mode==item['raw'];trigger_id=mode['_attackTrigger']['m_PathID'];trigger=objects[trigger_id].read_typetree();assert trigger==comps[str(trigger_id)]['raw'];go_id=trigger['m_GameObject']['m_PathID'];go=objects[go_id].read_typetree();members=[r['component']['m_PathID'] for r in go['m_Component']];assert trigger_id in members
            selectors=[int(pid) for pid,c in comps.items() if c['native_class']=='AdvancedSelector' and c['raw']['m_GameObject']['m_PathID']==go_id];assert len(selectors)==1 and selectors[0] in members
            combat_id=mode['_combat']['m_PathID'];combat=objects[combat_id].read_typetree();assert combat==comps[str(combat_id)]['raw'];assert combat['_selector']['m_PathID']==0 and combat['_selectTargetSource']==2
            binding_evidence.append({'owner':owner,'mode_path_id':int(mode_id),'trigger_path_id':trigger_id,'gameobject_path_id':go_id,'actual_gameobject_components':members,'unique_same_go_selector_path_id':selectors[0],'ranged_attack_path_id':combat_id,'actual_select_target_source':combat['_selectTargetSource'],'source_scope':'exact mode PPtr -> trigger same GO unique selector; INPUT_TARGET2 inherited targeting math bridge','native_body_pending':'Trigger_GetSelector and AttackWrapper target forwarding method body unknown'})
    p['manifest']={'id':'m25/source_qualification_profiles','metadata':{'builder_sha256':sha(__file__),'fixture_helper_sha256':sha(Path(__file__).with_name('test_eligibility.py')),'source_binding_evidence':binding_evidence,'source_locks':{str(mother_path.relative_to(ROOT)).replace(chr(92),'/'):sha(mother_path),str(audit_path.relative_to(ROOT)).replace('\\','/'):sha(audit_path),**{'../'+r['source']['path']:r['source']['sha256'] for r in records}},'implementation_sha256':implementation_digest(),'source_profiles':records,'scope':'exact source fields with model qualification; standalone synthetic geometry/actors, not stage wrapper','client_verified':False,'client_pending':['native ValidateTarget/getter bodies','source-relative side interpretation','neutral/default typed state policy','target-free cause aggregate','camouflage capability resolution'],'binding_scope':'exact mode/trigger/same-GO source chain above; inherited INPUT_TARGET forwarding algorithm remains client pending','native_state_writers':['token HEAL_FREE7','EMP INVINCIBLE5/STUNNED0'],'synthetic_status_extension':'target_free/camouflage explicit states exercise generic model; no recorded current-source writer asserted'}}
    Compiler().compile(p);return p
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8');OUT.parent.mkdir(parents=True,exist_ok=True)
    if a.check:assert OUT.read_bytes()==b
    else:OUT.write_bytes(b)
    print(json.dumps({'passed':True,'check':a.check,'selectors':len(p['selectors']),'package_sha256':sha(OUT),'core':implementation_digest()}))
