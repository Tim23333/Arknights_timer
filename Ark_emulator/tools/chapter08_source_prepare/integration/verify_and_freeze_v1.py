"""Fresh read-only guards of C8 extracted bytes/objects/BSON/DB and source copies."""
import json,hashlib,base64,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));BASE=ROOT/'packages/campaign/chapter08_source_prepare/integration'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifest=BASE/'source.manifest.v1.json';m=json.loads(manifest.read_bytes());assert m['source_before']==m['source_after'];assert all(sha(Path(p))==h for p,h in m['source_after'].items());plan=json.loads((BASE/'source.plan.v1.json').read_bytes());nativeDir=ROOT/'packages/campaign/native_reference';assert plan['selected_display_ids']=={'main_08-16':'JT8-2','main_08-17':'JT8-3'}
 from tools.build_mainline_dependencies import resolve_enemy,DEFAULT_DB
 db=json.loads(DEFAULT_DB.read_bytes())
 for k,s in plan['stages'].items():assert s['native_document']==json.loads((nativeDir/(k+'.json')).read_bytes())
 for v in plan['variants'].values():assert v['native_enemy']==resolve_enemy(db,v['native_reference'])
 counts={'stage_documents':2,'exact_variants':8,'BSON_documents':0,'Spine_payloads':0,'binary_stages':0,'external_PPtr_objects':0}
 for n in ['enemies.native.v1.json','environment.native.v1.json','predefines.native.v2.json']:
  d=json.loads((BASE/n).read_bytes())
  for record in d.get('bson_templates',{}).get('templates',{}).values():assert hashlib.sha256(base64.b64decode(record['document_base64'])).hexdigest()==record['document_sha256'];counts['BSON_documents']+=1
  for a in d.get('animations',{}).values():
   if 'payload_base64' in a:assert hashlib.sha256(base64.b64decode(a['payload_base64'])).hexdigest()==a['payload_sha256'];counts['Spine_payloads']+=1
 supplement=json.loads((BASE/'source.supplement.v1.json').read_bytes())
 for refs in supplement['binary_stages'].values():
  for ref in refs:assert hashlib.sha256(base64.b64decode(ref['raw_base64'])).hexdigest()==ref['sha'];counts['binary_stages']+=1
 for ref in supplement['external_PPtr_objects']:assert ref['status']=='exact_external_object_present';counts['external_PPtr_objects']+=1
 assert counts['Spine_payloads']==8;pred=json.loads((BASE/'predefines.native.v2.json').read_bytes());assert len(pred['stages']['level_main_08-17']['instances'])==10 and len(pred['prefabs']['trap_021_flame']['components'])==5;assert pred['stages']['level_main_08-16']['instances']==[]
 out=ROOT/'validation/campaign/chapter08_source_prepare_integration_v1';assert not out.exists();out.mkdir(parents=True);before={p:h for p,h in m['source_after'].items()};files=list(BASE.glob('*.json'))+list(Path(__file__).parent.glob('*.py'));before.update({str(p):sha(p) for p in files});after={p:sha(Path(p)) for p in before};assert before==after;report={'passed':True,'read_only_fresh_counts':counts,'source_before':before,'source_after':after,'scope':'Byte/JSON exact fixedDB/native stage extraction + payload SHA and external object existence. Source only, not C8 mechanics or client/game accuracy. All25 referenced Buffids queried, only1olderFBrow; remaining24 inline/version gaps explicit. Local20260831 versus20250327trap source not aligned. Opera roots absent from available local battle CABs;17rawactions retained.','runtime_authored':False,'whole_stage_executed':False};f=out/'verification.json';f.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
 for p in files:
  dest=out/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);assert sha(p)==sha(dest)
 freeze={'source_manifest_sha':sha(manifest),'mechanism_plan_sha':sha(BASE/'mechanism.plan.v1.json'),'fresh_verification':{'path':str(f),'sha':sha(f)},'frozen_files':{str(p):sha(p) for p in files},'source_before':before,'source_after':after,'source_stage_counts':m['stages'],'scope':report['scope'],'Root_consumer_assignment':'enemy_1108_uterer Root tools/chapter08_ordinary +packages/chapter08_consumers/uterer; source extract does not write consumers','runtime_authored':False,'whole_stage_executed':False,'client_verified':False};p=out/'freeze.json';p.write_text(json.dumps(freeze,indent=2)+'\n',encoding='utf8');print(json.dumps({'freeze_sha':sha(p),'verification_sha':sha(f),'counts':counts,'pins':len(before)}))
if __name__=='__main__':main()
