"""Prepare timing/cell-only response to an actual Plosis missing-SP rejection."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source=OUT/'compact.commands.public_v3.json';assert sha(source)=='c60aa77b8083beb9d83bd9d0e515927658b5f45a7d48ac40d08de597b91d8fe1';rows=json.loads(source.read_bytes());changes=[]
 for c in rows:
  if c.get('source')=='c409_plosis' and c['action']=='skill':changes.append({'before':dict(c),'resolution':'Wait actual15seconds periodic recovery from real initialSP85 to cost100'});c['at']=2400;changes[-1]['after']=dict(c)
  elif c.get('source')=='c409_plosis' and c['action']=='withdraw':changes.append({'before':dict(c)});c['at']=2430;changes[-1]['after']=dict(c)
  elif c.get('alias')=='c409_angel' and c['action']=='deploy':changes.append({'before':dict(c),'resolution':'Keep own actors at most2 and avoid Plosis occupied high tile'});c['row']=4;c['col']=5;changes[-1]['after']=dict(c)
 assert len(changes)==3;rows.sort(key=lambda c:c['at']);commands=OUT/'compact.commands.public_v4.prepared.json';receipt=OUT/'runthrough_launch.public_v4.prepared.json'
 if commands.exists() or receipt.exists():raise ValueError('Preserve later input')
 commands.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8',newline='');launch=json.loads((OUT/'runthrough_launch.public_v3.prepared.json').read_bytes());launch.update(commands=str(commands),commands_sha=sha(commands),status='Prepared timing/cell revision only; existing V3 full run continues with original hashes',command_revision={'observed_actual_failure':{'time':2250,'source':'c409_plosis','ability':'ability/plosis_s2_first_packet','reason':'insufficient resource sp'},'original_commands_sha':sha(source),'changes':changes,'attributes_resources_and_stage_mechanisms_changed':False});receipt.write_text(json.dumps(launch,indent=2)+'\n',encoding='utf8',newline='');assert sha(source)=='c60aa77b8083beb9d83bd9d0e515927658b5f45a7d48ac40d08de597b91d8fe1';print(json.dumps({'commands_sha':sha(commands),'launch_sha':sha(receipt)}))
if __name__=='__main__':main()
