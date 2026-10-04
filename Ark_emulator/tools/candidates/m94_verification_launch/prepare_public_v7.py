"""One logic tick after actual host SP15 settlement; no numeric/core changes."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source=OUT/'compact.commands.public_v6.prepared.json';assert sha(source)=='e36bab925241438200ca31d31d6e17860607b5912221684fa038c375fc254982';rows=json.loads(source.read_bytes());selected=[c for c in rows if c.get('ability')=='ability/kalts_host_s3'];assert len(selected)==1 and selected[0]['at']==3600;selected[0]['at']=3601;rows.sort(key=lambda c:c['at']);commands=OUT/'compact.commands.public_v7.prepared.json';receipt=OUT/'public_v7_timing.prepared.json'
 if commands.exists() or receipt.exists():raise ValueError('Preserve new operation input')
 commands.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8',newline='');report={'source_commands_sha':sha(source),'commands_sha':sha(commands),'only_change':'Host S3 public command tick3600 ->3601','actual_observation':'V6 host3570 recovery13->14; public command3600 runs before recovery3600 changes14->15, producing legitimate insufficient-SP rejection. This revision waits for that actual committed15.','previous_running_input_unchanged':True,'core_or_attributes_or_resource_grants':False,'prepared_only':True,'whole_stage_executed':False};receipt.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'commands_sha':sha(commands),'receipt_sha':sha(receipt)}))
if __name__=='__main__':main()
