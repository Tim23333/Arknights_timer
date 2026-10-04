"""Retain original command rejection and remove only forbidden manual auto skill."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 original=OUT/'runthrough_launch.prepared.json';old=json.loads(original.read_bytes());cp=OUT/'compact.commands.public_v2.json';launch=OUT/'runthrough_launch.public_v2.prepared.json'
 if cp.exists() or launch.exists():raise ValueError('Preserve revised inputs')
 proof=OUT/'compact_public1600.verification.json';assert sha(proof)=='b447aa659d6d5316921655ddc545df154b71196b0bdd7349e6708b1e21950726';report=json.loads(proof.read_bytes());rejections=[e for e in report['command_events'] if e['type']=='command.rejected'];assert len(rejections)==1
 reason=rejections[0];assert reason['time']==1470 and reason['payload']['action']['ability']=='ability/liskam_s1' and reason['payload']['reason']=='Automatic-only ability cannot be activated by a player command'
 source=Path(old['commands']);rows=json.loads(source.read_bytes());revised=[c for c in rows if not (c['at']==1470 and c.get('ability')=='ability/liskam_s1')];assert len(revised)==len(rows)-1
 cp.write_text(json.dumps(revised,indent=2)+'\n',encoding='utf8',newline='');old.update(commands=str(cp),commands_sha=sha(cp),status='Prepared revised public prefix; forbidden manual automatic-only action removed, original rejection preserved',revision={'original_commands':str(source),'original_commands_sha':sha(source),'removed':reason,'actual_prefix_report':str(proof),'actual_prefix_report_sha':sha(proof),'automatic_ability_policy':'Retain original system-driven auto_only activation; no stats/SP/status/cooldown grants'})
 launch.write_text(json.dumps(old,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'commands_sha':sha(cp),'launch_sha':sha(launch)}))
if __name__=='__main__':main()
