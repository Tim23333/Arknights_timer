"""Read-only admission gate and finite overlay inspection."""
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter10_stage_source_peer_v1.source_preflight import exact
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def differences(a,b,path='$'):
    if type(a)!=type(b):return [{'path':path,'before':type(a).__name__,'after':type(b).__name__}]
    if isinstance(a,dict):
        rows=[]
        for k in set(a)|set(b):
            if k not in a or k not in b:rows.append({'path':path+'.'+k,'before':a.get(k,'<absent>'),'after':b.get(k,'<absent>')})
            else:rows.extend(differences(a[k],b[k],path+'.'+k))
        return rows
    if isinstance(a,list):
        if len(a)!=len(b):return [{'path':path,'before_length':len(a),'after_length':len(b)}]
        return [d for i,(x,y) in enumerate(zip(a,b)) for d in differences(x,y,path+'['+str(i)+']')]
    return [] if a==b else [{'path':path,'before':a,'after':b}]
def main():
    original=ROOT/'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v3.life99999.json';finite=ROOT/'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v3.life99999.finite_v1.json';checker=ROOT/'tools/chapter10_whole_admission_v1/check.py'
    a=json.loads(original.read_bytes());b=json.loads(finite.read_bytes());exact(a['definitions'],b['definitions']);delta=differences(a,b)
    report={'schema':'ark-sim/whole-admission-static-review/v1','checker_sha256':sha(checker),'package_sha256':sha(finite),'parent_sha256':sha(original),'typed_definitions_unchanged':True,'actual_overlay_differences':delta,'whole_execution_started_by_review':False,'core_approved':False,'static_findings':[
      {'severity':'bounded_gate_present','detail':'Missing completed full/baseline/prefix reports install explicit failed checks; nonzero exit/admittedFalse. Fixed core/freeze/whole package/commands SHA and imported runtime path are checked. Gate cannot grant whole-stage completion by design.'},
      {'severity':'tighten','detail':'Full actual_modules all(...) is vacuously true for empty map. Require nonempty module attribution and exact expected candidate inventory membership, not only arbitrary paths under a runtime.'},
      {'severity':'tighten','detail':'Full cases checks1219 length/status but not uniqueness or exact nodeid set. Duplicate case rows could satisfy count while dropping another test. Bind expected collected nodeids/catalog108 runner identity.'},
      {'severity':'tighten','detail':'Source report is not pinned to the approved receipt SHA or required finite package. It accepts any current guard dictionary with self-declared source_input_approved/core flags. Pin known source-review receipt and ensure original/V3 package SHA are in that review guard.'},
      {'severity':'scope','detail':'Finite whole-input SHA authenticates this particular root file but its overlay differences were not in original typed source review. Explicitly audit permitted scene objective/metadata changes against unchanged typed definitions and routes.'},
      {'severity':'scope','detail':'Completed runtime reports are trusted local producer evidence, not cryptographic execution authentication. This checker should not imply arbitrary edited JSON passed flags prove execution. Preserve original completed reports and pin consumed producer/helper identities.'}
    ],'review_scope':'Static gate condition coverage. No active tests started; pending full/baseline/prefix remain pending. No requested counter simulated.'}
    out=ROOT/'validation/campaign/chapter10_stage_assembly_peer_v2/admission.static.review.v1.json';assert not out.exists();out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'report_sha256':sha(out),'overlay_differences':delta},ensure_ascii=False))
if __name__=='__main__':main()
