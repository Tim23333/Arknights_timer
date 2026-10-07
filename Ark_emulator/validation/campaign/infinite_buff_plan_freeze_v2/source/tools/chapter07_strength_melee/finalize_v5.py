"""New source identity consuming actual-duration Infinity candidate v2."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 outputs=[]
 for parent in (ROOT/'packages/campaign/chapter07_strength_melee').glob('*.v4.json'):
  p=json.loads(parent.read_bytes());p['manifest']['metadata']['required_runtime']='aa919c9cbd380cf74544d22b4cdebaa9d333c97eed8b21de5b8d8e5186c77d2d';p['manifest']['metadata']['source_locks'].update({str(parent):sha(parent),str(Path(__file__)):sha(Path(__file__))});p['manifest']['id']=p['manifest']['id'].replace('/v4','/v5');out=parent.with_name(parent.name.replace('.v4.json','.v5.json'));assert not out.exists();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');outputs.append({'path':str(out),'sha':sha(out)})
 print(json.dumps(outputs))
if __name__=='__main__':main()
