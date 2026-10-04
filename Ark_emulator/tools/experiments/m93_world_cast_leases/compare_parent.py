from pathlib import Path
import hashlib,json,subprocess,sys,importlib.util
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m93_world_cast_leases'
spec=importlib.util.spec_from_file_location('m78_compare',ROOT/'tools/experiments/m78_attachments/compare_parent.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
def main():
 values=[];runs=[]
 for label,name in [('parent','campaign_m78_owned_attachment_candidate'),('candidate','campaign_m93_world_cast_leases_candidate')]:
  path=OUT/(label+'-no-feature-full-values.json');assert not path.exists()
  subprocess.run([sys.executable,str(Path(__file__)),'--worker',str(ROOT.parent/'unpack_work'/name),str(path)],check=True)
  values.append(json.loads(path.read_bytes()));runs.append({'label':label,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 actual=a.differences(*values);allowed=sorted('/'+case+'/'+part+'/runtime_fingerprint' for case in values[0] for part in ('snapshot','checkpoint','replay'))
 assert sorted(d['path'] for d in actual)==allowed,actual
 report={'passed':True,'differences':actual,'all_other_values_types_and_float_bits_equal':True,'runs':runs}
 with (OUT/'no_feature_comparison.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
 print(json.dumps({'passed':True,'differences':len(actual)}))
if __name__=='__main__':
 if len(sys.argv)>1:a.worker(sys.argv[2],sys.argv[3])
 else:main()
