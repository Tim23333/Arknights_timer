import pytest,json
from copy import deepcopy
from pathlib import Path
from tools.chapter06_npcs.normalize_inputs import normalized
ROOT=Path(__file__).resolve().parents[3]
@pytest.mark.parametrize('field,value',[('favorPoint',False),('potentialRank',False),('level',True),('favorPoint',1),('potentialRank',1)])
def test_native_input_wrong_boolean_or_nonzero_value_rejected(field,value):
 source=json.loads((ROOT/'packages/campaign/chapter06_predefines/source.reference.json').read_bytes());r=deepcopy(source['stages']['level_main_06-15']['instances'][0]);r['raw_native']['inst'][field]=value
 with pytest.raises(ValueError):normalized(r)
@pytest.mark.parametrize('value',[True,0,2])
def test_no_skill_profile_cannot_fabricate_selected_skill(value):
 source=json.loads((ROOT/'packages/campaign/chapter06_predefines/source.reference.json').read_bytes());r=deepcopy(source['stages']['level_main_06-15']['instances'][1]);r['raw_native']['skillIndex']=value
 with pytest.raises(ValueError):normalized(r)
