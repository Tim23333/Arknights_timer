import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v12_candidate'
OUT=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v13_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):
 code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
 return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()
def main():
 assert core(BASE)=='6192789537ba5250da2cd781f6583a8b7ce7dccfcfba4a5bb9fc5f535674d419' and not OUT.exists()
 shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 file=OUT/'ark_sim/domains/buff_application.py';text=file.read_text(encoding='utf8')
 old="        sg, tg = _generation(ctx, source), _generation(ctx, target)";new="        sg, tg = _generation(ctx, source), _generation(ctx, target)\n        def source_identity(): return (ctx.alive(source), ctx.active(source), ctx.get(source, ('runtime', 'state')), _generation(ctx, source))\n        source_at_entry = source_identity()";assert text.count(old)==1;text=text.replace(old,new)
 old="if not source_allowed() or not ctx.active(target) or _generation(ctx, source) != sg or _generation(ctx, target) != tg:"
 new="if not source_allowed() or source_identity() != source_at_entry or not ctx.active(target) or _generation(ctx, source) != sg or _generation(ctx, target) != tg:"
 assert text.count(old)==1;text=text.replace(old,new);file.write_text(text,encoding='utf8',newline='')
 out=ROOT/'validation/campaign/retained_buff_payload_v13/composition.json';out.parent.mkdir(parents=True,exist_ok=True)
 report={'core':core(OUT),'parent_core':core(BASE),'old_sha':sha(BASE/'ark_sim/domains/buff_application.py'),'new_sha':sha(file),'scope':'Stop remaining Buff plan after source alive/active/state/incarnation changes during callback; pre-impact retired source retained unchanged'}
 with out.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
 print(json.dumps(report))
if __name__=='__main__':main()
