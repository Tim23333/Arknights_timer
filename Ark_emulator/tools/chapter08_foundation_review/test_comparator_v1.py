import json
from copy import deepcopy
import pytest
from tools.chapter08_foundation_review.compare_pair_v1 import PAIR,compare
@pytest.mark.parametrize('field',['context','value','cache','order','unknownFPpath'])
def test_pair_comparator_rejects_semantic_or_order_changes_not_only_terminal(field):
 a=json.loads((PAIR/'parent/capture.json').read_bytes());b=json.loads((PAIR/'candidate/capture.json').read_bytes());c=b['cases'][0]
 if field=='cache':c['attribute_cache_entries'][0][1][0]+=1
 elif field=='value':c['checkpoint']['kernel']['events']['records'][0]['payload']['value']+=1
 elif field=='context':c['checkpoint']['kernel']['events']['records'][0]['payload']['trace']['context']['time']+=1
 elif field=='order':c['input']['manifest']=dict(reversed(list(c['input']['manifest'].items())))
 else:c['snapshot']['mysterious_runtime_fingerprint']=c['actual_runtime_fingerprint']
 with pytest.raises(AssertionError):compare(a,b)
