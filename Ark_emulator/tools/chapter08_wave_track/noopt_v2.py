"""Fresh fixed-parent and candidate no-opt capture; only implementation identity differs."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT.parent/'unpack_work/campaign_chapter08_joint_v4_candidate';CAND=ROOT.parent/'unpack_work/campaign_wave_track_v2_candidate';OUT=Path('E:/ArkSimEvidence/wave_track_noopt_v2');P='20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30';C='d12060329b762439077c4c03110120c87e486fd462bf6c941d6636a759543f52'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 helper=ROOT/'tools/chapter06_environment_consumer/capture_noopt_v1.py';paths=[helper,Path(__file__),ROOT/'packages/custom/custom_guard.json',ROOT/'packages/ark_content/level_main_00_01.json',ROOT/'scenarios/level_main_00_01/commands.json']
 for runtime in (BASE,CAND):paths+=list((runtime/'ark_sim').rglob('*.py'))+list((runtime/'ark_sim').rglob('*.json'))
 before={str(p):sha(p) for p in paths};OUT.mkdir(parents=True,exist_ok=True)
 for label,runtime,core in [('parent',BASE,P),('candidate',CAND,C)]:subprocess.run([sys.executable,str(helper),'--runtime',str(runtime),'--core',core,'--output',str(OUT/(label+'.json'))],cwd=ROOT,check=True)
 a=json.loads((OUT/'parent.json').read_bytes());b=json.loads((OUT/'candidate.json').read_bytes());diff=[]
 def compare(a,b,path=''):
  if type(a) is not type(b):diff.append(path);return
  if isinstance(a,dict):
   if a.keys()!=b.keys():diff.append(path);return
   for k in a:compare(a[k],b[k],path+'/'+k)
  elif isinstance(a,list):
   if len(a)!=len(b):diff.append(path);return
   for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
  elif a!=b:diff.append(path)
 compare(a,b);assert set(diff)=={'/core'}|{'/cases/'+str(i)+'/snapshot/runtime_fingerprint' for i in range(3)};after={str(p):sha(p) for p in paths};assert before==after;out=ROOT/'validation/campaign/chapter08_wave_track_noopt_v2/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':True,'parent_core':P,'core':C,'source_before':before,'source_after':after,'capture_pins':{str(p):sha(p) for p in OUT.glob('*.json')},'all_values_compared':True,'only_identity_differences':diff,'0_1_prefix150_only':True,'custom_standard30_and_custom30':True,'full_0_1_passed':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'diff':diff}))
if __name__=='__main__':main()
