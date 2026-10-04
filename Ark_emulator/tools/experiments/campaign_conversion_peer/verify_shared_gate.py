import sys,json,hashlib,tempfile
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m12_projection_candidate'));sys.path.insert(1,str(ROOT))
from tools.campaign_model_acceptance import shared_witness_gate
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
results=[]
for label in ('m14','00_11'):
 p=ROOT/f'validation/campaign/shared_actor_scope_{label}_gate_review.json';review=json.loads(p.read_bytes());rr={'path':str(p.relative_to(ROOT)),'sha256':sha(p)};receipt={'shared_scope_reviews':[rr]};expected={'content_sha256':review['target_content_sha256'],'implementation_sha256':review['implementation_sha256']}
 for row in review['approved_cases']:
  ref={'path':row['source_evidence_path'],'sha256':row['source_evidence_sha256'],'case':row['case'],'helper_path':row['helper_path'],'helper_sha256':row['helper_sha256'],'shared_scope_review':rr}
  assert shared_witness_gate(ROOT,ref,receipt,expected)==review['source_content_sha256']
 negatives=[]
 with tempfile.TemporaryDirectory(dir=ROOT/'tools/experiments/campaign_conversion_peer') as d:
  for change in ('wrong_target','wrong_helper','missing_receipt_scope','first_fixture_only','changed_reachable_definition','metadata_unreviewed','changed_source_artifact','static_fake_execution'):
   sr=deepcopy(review);row=next(x for x in sr['approved_cases'] if ('config_source' in x['case'])==(change=='static_fake_execution'));pf=json.loads((ROOT/row['proof']['path']).read_bytes());ex=deepcopy(expected)
   if change=='wrong_target':ex['content_sha256']='0'*64
   elif change=='first_fixture_only':pf['all_fixtures_accounted_for']=False
   elif change=='changed_reachable_definition':pf['reachable_definitions_equal']=False
   elif change=='metadata_unreviewed':pf['metadata_nonconsumption_reviewed']=False
   elif change=='static_fake_execution':pf['target_case_executed']=True
   proof=Path(d)/'proof.json';proof.write_text(json.dumps(pf),encoding='utf8');row['proof']={'path':str(proof.relative_to(ROOT)),'sha256':sha(proof)}
   rpath=Path(d)/'review.json';rpath.write_text(json.dumps(sr),encoding='utf8');rref={'path':str(rpath.relative_to(ROOT)),'sha256':sha(rpath)};rc={'shared_scope_reviews':[rref]}
   ref={'path':row['source_evidence_path'],'sha256':row['source_evidence_sha256'],'case':row['case'],'helper_path':row['helper_path'],'helper_sha256':row['helper_sha256'],'shared_scope_review':rref}
   if change=='wrong_helper':ref['helper_path']='tools/nonexistent_peer_helper.py'
   elif change=='changed_source_artifact':ref['sha256']='0'*64
   elif change=='missing_receipt_scope':rc['shared_scope_reviews']=[]
   try:shared_witness_gate(ROOT,ref,rc,ex)
   except ValueError as e:negatives.append({'case':change,'rejected':True,'reason':str(e)})
   else:raise AssertionError(change)
 results.append({'target':label,'accepted_bindings':len(review['approved_cases']),'review_sha256':sha(p),'negative_cases':negatives})
report={'passed':True,'gate_source_sha256':sha(ROOT/'tools/campaign_model_acceptance.py'),'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(__file__),'result':'passed'}],'cases':results,'scope':'Actual shared_witness_gate calls; not a whole receipt or native validation'}
(ROOT/'validation/campaign/shared_actor_scope_gate_peer.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'positive_bindings':sum(x['accepted_bindings'] for x in results),'negative_rejections':sum(len(x['negative_cases']) for x in results)}))
