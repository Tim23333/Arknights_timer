"""Same-shape adversarial FP fields cannot use identity exemptions."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from verify import pair
original={'runtime_fingerprint':'1'*64,'context':{'runtime_fingerprint':'2'*64,'program_fingerprint':'3'*64},'cached_calc':{'rule_fingerprint':'4'*64,'rule_runtime_fingerprint':'5'*64},'metadata':{'unrelated_fingerprint':'6'*64}}
allowed={'$.runtime_fingerprint':('1'*64,'a'*64)}
accepted=copy.deepcopy(original);accepted['runtime_fingerprint']='a'*64;pair(original,accepted,allowed)
checks=[]
for owner,key in [('context','runtime_fingerprint'),('context','program_fingerprint'),('cached_calc','rule_fingerprint'),('cached_calc','rule_runtime_fingerprint'),('metadata','unrelated_fingerprint')]:
 changed=copy.deepcopy(accepted);changed[owner][key]='b'*64
 try:pair(original,changed,allowed)
 except AssertionError:checks.append(owner+'.'+key)
 else:raise AssertionError('arbitrary name exemption '+owner+'.'+key)
out=Path(__file__).resolve().parents[2]/'validation/campaign/chapter09_invisible_independent_final/identity.adversarial.v1.json'
out.write_text(json.dumps({'known_identity_accepts':True,'same_shape_untrusted_FP_changes_rejected':checks,'passed':True},indent=2)+'\n',encoding='utf8')
print(json.dumps({'passed':True,'rejected':len(checks)}))
