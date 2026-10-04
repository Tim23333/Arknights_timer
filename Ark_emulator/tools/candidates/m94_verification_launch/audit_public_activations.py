"""Audit every fixed-roster activation and prepare manual commands allowed by content."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 previous=OUT/'runthrough_launch.public_v2.prepared.json';launch=json.loads(previous.read_bytes());package=Path(launch['package']);p=json.loads(package.read_bytes());defs={d['id']:d for section in ('definitions','entities','abilities','rules') for d in p.get(section,[])};audit=[];forbidden={}
 for uid in p['scenarioDraft']['roster']:
  for ability in defs[uid]['components'].get('abilities',[]):
   a=defs[ability];activation=a.get('activation',{});params={**a.get('parameters',{}),**activation.get('parameters',{})};auto=bool(params.get('auto_only')) or activation.get('mode')!='manual';audit.append({'unit':uid,'ability':ability,'mode':activation.get('mode'),'auto_only':params.get('auto_only',False),'public_manual_allowed':not auto,'costs':activation.get('costs',[]),'source_condition':activation.get('condition')})
   if auto:forbidden[ability]=audit[-1]
 oldcommands=Path(launch['commands']);rows=json.loads(oldcommands.read_bytes());removed=[c for c in rows if c.get('action')=='skill' and c['ability'] in forbidden];new=[c for c in rows if c not in removed];commands=OUT/'compact.commands.public_v3.json';dest=OUT/'runthrough_launch.public_v3.prepared.json';report=OUT/'activation_audit.public_v3.json'
 if any(x.exists() for x in (commands,dest,report)):raise ValueError('Preserve audit/commands')
 commands.write_text(json.dumps(new,indent=2)+'\n',encoding='utf8',newline='');details={'package_sha':sha(package),'previous_launch_sha':sha(previous),'previous_commands_sha':sha(oldcommands),'all_fixed12_activations':audit,'removed_forbidden_manual_commands':removed,'automatic_witness_policy':'Inspect real ability.started, owned SP/charge and event identity from actual complete events; no public skill call or synthetic SP/status/numeric writes.'};report.write_text(json.dumps(details,indent=2)+'\n',encoding='utf8',newline='')
 launch.update(commands=str(commands),commands_sha=sha(commands),status='Prepared fully audited public manual activation commands; automatic-only skills retain real automatic runtime conditions',activation_audit=str(report),activation_audit_sha=sha(report));dest.write_text(json.dumps(launch,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'commands_sha':sha(commands),'launch_sha':sha(dest),'removed':removed,'activation_audit_sha':sha(report)}))
if __name__=='__main__':main()
