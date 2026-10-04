"""Prepare real SP waiting windows and another legal bird tile after V3 receipts."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source=OUT/'compact.commands.public_v5.prepared.json';assert sha(source)=='96c862d02d699f7c4662243ae8a650dca4899f877d0671d0d20861d053cbe12e';rows=json.loads(source.read_bytes());changes=[]
 for c in rows:
  before=dict(c)
  if c.get('source')=='c409_lisa' and c['action']=='skill':c['at']=4110
  elif c.get('source')=='c409_lisa' and c['action']=='withdraw':c['at']=4140
  elif c.get('source')=='c409_weedy' and c['action']=='skill':c['at']=4290
  elif c.get('source')=='c409_weedy' and c['action']=='withdraw':c['at']=4350
  elif c.get('alias')=='c409_cgbird' and c['action']=='deploy':c['row']=1;c['col']=2
  elif c.get('source')=='c409_cgbird' and c['action']=='skill':c['at']=4440
  elif c.get('source')=='c409_cgbird' and c['action']=='withdraw':c['at']=4500
  if c!=before:changes.append({'before':before,'after':dict(c)})
 assert len(changes)==7;rows.sort(key=lambda c:c['at']);commands=OUT/'compact.commands.public_v6.prepared.json';receipt=OUT/'runthrough_launch.m96_v6.prepared.json'
 if commands.exists() or receipt.exists():raise ValueError('Preserve input')
 commands.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8',newline='');launch=json.loads((OUT/'runthrough_launch.m96_v5.prepared.json').read_bytes());launch.update(commands=str(commands),commands_sha=sha(commands),status='Prepared revised command timings and legal cell; no source/attributes/SP/HP/DP/slots modifications',additional_command_revision={'source_commands_sha':sha(source),'changes':changes,'original_actual_rejections':[{'at':3810,'source':'c409_lisa','reason':'insufficient resource sp'},{'at':4200,'source':'c409_weedy','reason':'insufficient resource sp'},{'at':4590,'source':'c409_cgbird','reason':'Ability source is not active'}],'operation_only_policy':'Wait original periodic SP (Lisa50->70 in20s,Weedy20->33 in13s,Bird115->120 in5s), keep summon cost10 and allow actual death/control rejections without any value grants','runtime_scope':'Prepared; no success claim until actual commands and lifecycle evidence are executed'})
 receipt.write_text(json.dumps(launch,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'commands_sha':sha(commands),'launch_sha':sha(receipt),'last_command':rows[-1]['at']}))
if __name__=='__main__':main()
