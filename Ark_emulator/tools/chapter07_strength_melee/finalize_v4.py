"""New content pins explicit Infinity-capable runtime and provider, old v1-v3 retained."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 outputs=[]
 for parent in (ROOT/'packages/campaign/chapter07_strength_melee').glob('*.v3.json'):
  p=json.loads(parent.read_bytes());p['manifest']['metadata']['required_runtime']='b20d8bd43e6db219186dca4c01c759b4fa3b44262bddbb5173ab952bf256b188';p['manifest']['metadata']['source_locks'].update({str(parent):sha(parent),str(ROOT/'tools/chapter07_strength_melee/policies_v2.py'):sha(ROOT/'tools/chapter07_strength_melee/policies_v2.py'),str(Path(__file__)):sha(Path(__file__))});p['manifest']['metadata']['infinite_application_policy']='Explicit duration_seconds None; actual Buff has no declared finite duration and no duration_rule. Existing permanent lifecycle, not duration0 substitute.';p['manifest']['id']=p['manifest']['id'].replace('/v3','/v4');out=parent.with_name(parent.name.replace('.v3.json','.v4.json'));assert not out.exists();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');outputs.append({'path':str(out),'sha':sha(out)})
 print(json.dumps(outputs))
if __name__=='__main__':main()
