from tools.chapter09_stage918_peer_v2.audit import *
import pytest

def test_actual_type_exact_source_a13_plan90075_static_gate():
 p=json.loads(PACKAGE.read_bytes());result=audit(p);REPORT.mkdir(parents=True,exist_ok=True);(REPORT/'static.actual.json').write_text(json.dumps({'core':CORE,'actual_passed':True,'input_sha':sha(PACKAGE),'commands_sha':sha(COMMANDS),'facts':result,'source_guard':guard()==START},indent=2),encoding='utf8')

@pytest.mark.parametrize('change',['missing_raw_action','bool_as_count','wrong_row','raw_alias_rename','Buffmapping_missing'])
def test_source_counterfacts_fail_closed_independent_audit(change):
 p=json.loads(PACKAGE.read_bytes())
 if change=='missing_raw_action':del p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][0]['metadata']['native_action']['hiddenGroup']
 elif change=='bool_as_count':p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][0]['count']=True
 elif change=='wrong_row':p['scenarioDraft']['initialEntities'][0]['position']['row']+=1
 elif change=='raw_alias_rename':p['scenarioDraft']['initialEntities'][0]['parameters']['native_instance']['alias']='fixed_unique_alias'
 else:next(d for d in p['definitions'] if d['id']=='rule/ch9/demolition/push')['parameters']['status_definitions'].pop(next(iter(next(d for d in p['definitions'] if d['id']=='rule/ch9/demolition/push')['parameters']['status_definitions'])))
 with pytest.raises((AssertionError,KeyError)):audit(p)
 assert guard()==START
