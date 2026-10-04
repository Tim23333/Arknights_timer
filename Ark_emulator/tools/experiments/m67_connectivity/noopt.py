"""Separate-process full-value no-opt comparison; classify identity paths."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m67_connectivity/noopt'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    old=json.loads((ROOT/'validation/campaign/m64_connectivity/initial_tests.json').read_bytes())['actual_inputs'][0]['input']
    old['entities'][0]['components']['deployable'].pop('connectivity')
    old['rules']=[r for r in old['rules'] if r['id']!='rule/connected']
    old['scenarioDraft']['map']={'rows':2,'cols':4}
    input_file=OUT/'input.json';input_file.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    code='''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
assert implementation_digest()==sys.argv[4]
p=json.loads(Path(sys.argv[2]).read_bytes());s=Engine.create(Compiler().compile(p),seed=64057)
for at,row,col,alias in [(0,0,1,'first'),(1,1,2,'second')]:s.submit({'action':'deploy','definition':'unit/barrier','alias':alias,'position':{'row':row,'col':col}},at=at)
s.submit({'action':'withdraw','source':'first'},at=2);s.advance(5)
Path(sys.argv[3]).write_text(json.dumps(thaw({'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'replay':s.export_replay()}),ensure_ascii=False,indent=2)+'\\n',encoding='utf8',newline='\\n')
assert implementation_digest()==sys.argv[4]
'''
    runs=[('parent','campaign_m58_corrected_chapter03_candidate','1ef9635ee70a8159e0523156aeeb177329d19d12a26185b98b9d9fa55ea3c3d5'),
          ('candidate','campaign_m67_connectivity_snapshot_candidate','138cf9a4927f20162b207d07cb34441a41aabe887e0a06630fcd36cef9a6a07b')]
    for label,name,pin in runs:
        r=subprocess.run([sys.executable,'-c',code,str(ROOT.parent/'unpack_work'/name),str(input_file),str(OUT/(label+'.json')),pin],cwd=ROOT,capture_output=True,text=True)
        if r.returncode:raise ValueError(r.stdout+r.stderr)
    before=json.loads((OUT/'parent.json').read_bytes());after=json.loads((OUT/'candidate.json').read_bytes());diffs=[]
    def compare(a,b,path=''):
        if type(a)!=type(b):diffs.append({'path':path,'parent':a,'candidate':b});return
        if isinstance(a,dict):
            if set(a)!=set(b):diffs.append({'path':path,'parent_keys':list(a),'candidate_keys':list(b)});return
            for k in a:compare(a[k],b[k],path+'/'+str(k))
        elif isinstance(a,list):
            if len(a)!=len(b):diffs.append({'path':path,'parent_length':len(a),'candidate_length':len(b)});return
            for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
        elif a!=b:diffs.append({'path':path,'parent':a,'candidate':b})
    compare(before,after)
    roots={f'/{section}/{field}' for section in ('snapshot','checkpoint','replay') for field in ('program_fingerprint','runtime_fingerprint')}
    for diff in diffs:
        path=diff['path'];diff['kind']='root_identity' if path in roots else 'calculation_registry_identity' if '/events/' in path and '/trace/' in path and path.endswith('/runtime_fingerprint') else 'unclassified'
    report={'schema':'ark-sim/connectivity-noopt-comparison/v1','passed_declared_noopt_values':not any(d['kind']=='unclassified' for d in diffs),
        'all_actual_differences':diffs,'parent_event_count':len(before['snapshot']['events']),'candidate_event_count':len(after['snapshot']['events']),
        'source_sha256':hashlib.sha256(input_file.read_bytes()).hexdigest(),'scope':'Every value compared; explicit root/catalog trace identities retained, not recursively removed by key name',
        'source_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [input_file,OUT/'parent.json',OUT/'candidate.json',Path(__file__)]}}
    (OUT/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':report['passed_declared_noopt_values'],'differences':len(diffs),'unclassified':[d['path'] for d in diffs if d['kind']=='unclassified'],'events':report['candidate_event_count']}))


if __name__=='__main__':main()
