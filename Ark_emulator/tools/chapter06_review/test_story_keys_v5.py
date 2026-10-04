import json
from pathlib import Path
from copy import deepcopy
import pytest
from tools.chapter06_review.story_keys_v5 import convert,validate,digest,SCHEMA,POLICY
from tools.chapter06_review.stage_converter_v5 import compose
from tools.build_reference_stage_scenario_v4 import compose as old_compose
ROOT=Path(__file__).resolve().parents[2]
def source(code='06-15'):return json.loads((ROOT/'packages/campaign/native_reference'/('level_main_'+code+'.json')).read_bytes())
def definitions(n):return {r['inst']['characterKey']:'unit/proposed/'+r['inst']['characterKey']+'/source_config' for bucket in ['characterInsts','tokenInsts'] for r in n['predefines'].get(bucket) or []}
def profile(n):
 return {'schema':SCHEMA,'policy':POLICY,'native_id':'level_main_06-15','native_document_digest':digest(n),'bindings':[{'bucket':'characterInsts','index':i,'activation_key':r['inst']['characterKey'],'definition':definitions(n)[r['inst']['characterKey']]} for i,r in enumerate(n['predefines']['characterInsts']) if r['hidden'] and r['alias'] is None]}
def test_actual_three_keys_source_fields_and_no_input_mutation():
 n=source();before=deepcopy(n);p=profile(n);bindings=definitions(n);result=convert(n,'level_main_06-15',bindings,story_key_profile=p)
 assert n==before and result['native_predefines']==n['predefines'] and len(result['initial_entities'])==3
 keys=[a['key'] for w in n['waves'] for f in w['fragments'] for a in f['actions'] if a['actionType']=='ACTIVATE_PREDEFINED']
 assert {r['registration_key'] for r in result['initial_entities']}==set(keys)
 for i,item in enumerate(result['initial_entities']):
  raw=n['predefines']['characterInsts'][i];assert item['active'] is False and item.get('instanceAlias') is None and item['parameters']['native_instance']==raw
  assert item['position']=={'row':len(n['mapData']['map'])-1-raw['position']['row'],'col':raw['position']['col']} and item['facing']==raw['direction'].lower()
  assert raw['alias'] is None and raw['hidden'] is True and raw['skillIndex']==-1 and raw['inst']['level']==25 and raw['inst']['phase']=='PHASE_2'
 assert n['options']['characterLimit']==0 and n['options']['maxLifePoint']==1 and n['options']['initialCost']==0 and n['options']['costIncreaseTime']==9999
def test_null_alias_remains_rejected_without_optin():
 n=source()
 with pytest.raises(ValueError,match='explicit'):convert(n,'level_main_06-15',definitions(n))
@pytest.mark.parametrize('value',[0,1,'false',None])
def test_native_hidden_strict_bool(value):
 n=source();n['predefines']['characterInsts'][0]['hidden']=value
 with pytest.raises(ValueError,match='strict bool'):convert(n,'level_main_06-15',definitions(n),story_key_profile=profile(n))
@pytest.mark.parametrize('field,value',[('index',True),('index',-1),('index',99),('bucket','unknown'),('activation_key','amiya'),('activation_key','$avatar_amiya'),('activation_key',1),('definition',True),('definition','')])
def test_mapping_fields_strict(field,value):
 n=source();p=profile(n);p['bindings'][0][field]=value
 with pytest.raises(ValueError):convert(n,'level_main_06-15',definitions(n),story_key_profile=p)
def test_duplicate_character_key_ambiguity_rejects():
 n=source();n['predefines']['characterInsts'].append(deepcopy(n['predefines']['characterInsts'][0]))
 with pytest.raises(ValueError):convert(n,'level_main_06-15',definitions(n),story_key_profile=profile(n))
def test_duplicate_binding_identity_rejects():
 n=source();p=profile(n);p['bindings'].append(deepcopy(p['bindings'][0]))
 with pytest.raises(ValueError):convert(n,'level_main_06-15',definitions(n),story_key_profile=p)
def test_incomplete_bindings_rejects():
 n=source();p=profile(n);p['bindings'].pop()
 with pytest.raises(ValueError,match='Every hidden'):convert(n,'level_main_06-15',definitions(n),story_key_profile=p)
def test_duplicate_actual_activation_command_rejects():
 n=source();actions=n['waves'][0]['fragments'][1]['actions'];actions.append(deepcopy(next(a for a in actions if a['actionType']=='ACTIVATE_PREDEFINED')))
 with pytest.raises(ValueError,match='Duplicate story'):convert(n,'level_main_06-15',definitions(n),story_key_profile=profile(n))
def test_stale_source_profile_after_options_change_rejects():
 n=source();p=profile(n);n['options']['characterLimit']=12
 with pytest.raises(ValueError,match='identity'):convert(n,'level_main_06-15',definitions(n),story_key_profile=p)
def test_visible_record_cannot_retain_hidden_story_binding():
 n=source();p=profile(n);n['predefines']['characterInsts'][0]['hidden']=False;p['native_document_digest']=digest(n)
 with pytest.raises(ValueError,match='hidden null'):convert(n,'level_main_06-15',definitions(n),story_key_profile=p)
def test_alias_key_collision_across_buckets_rejects():
 n=source();r=deepcopy(n['predefines']['characterInsts'][0]);r['alias']='char_002_amiya';n['predefines']['tokenInsts']=[r]
 with pytest.raises(ValueError):convert(n,'level_main_06-15',definitions(n),story_key_profile=profile(n))
def test_definition_profile_mismatch_rejects():
 n=source();p=profile(n);p['bindings'][0]['definition']='unit/wrong'
 with pytest.raises(ValueError,match='disagrees'):convert(n,'level_main_06-15',definitions(n),story_key_profile=p)
@pytest.mark.parametrize('code',['05-09','05-10'])
def test_noopt_c5_full_conversion_equals_preserved_v4(code):
 n=source(code);n['branches']=None;p=convert(n,'same',definitions(n));b={r['id']:{'unit':'unit/'+r['id'],'motion':'WALK'} for r in n['enemyDbRefs']};tiles={'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}}
 assert compose(n,'same',b,tiles,predefined_profile=p)==old_compose(n,'same',b,tiles,predefined_profile=p)
def test_original_training_special_spawn_still_explicitly_rejected():
 n=source();p=profile(n);predefined=convert(n,'level_main_06-15',definitions(n),story_key_profile=p);b={r['id']:{'unit':'unit/'+r['id'],'motion':'WALK'} for r in n['enemyDbRefs']}
 with pytest.raises(ValueError,match='special native action'):compose(n,'level_main_06-15',b,{},predefined_profile=predefined,story_key_profile=p)
