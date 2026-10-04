"""Reproduce explicit retained Reborning modifiers on real waiting phase."""
import json
from tools.chapter07_boss.build_mechanism_v1 import OUT,UID,sha
def main():
 p=json.loads((OUT/'waiting.mechanism.v1.json').read_bytes());rid='rule/'+UID+'/waiting_stats_active';p['rules'].append({'id':rid,'kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':"'rebirth' in inputs.owner.components.runtime and inputs.owner.components.runtime.rebirth.phase == 'waiting' and inputs.instance.started_at == inputs.owner.components.runtime.rebirth.began_at"}})
 for b in p['buffs']:
  if b['id'].endswith('/reborning_stats'):b.update({'removal':{'on_source_death':'retain','on_target_death':'retain'},'duration_seconds':60,'active_rule':rid})
 p['manifest']['id']='package/ch7/patrt/waiting_owned_action_probe_v2';p['manifest']['metadata']['waiting_stats_retention']='SourceignoreDead1 Reborningmodifier liveswhileexactbegan_at waiting, duration60; retaininactiveowner explicitly, on_finish removes; defaultsource-death removal failure preserved.';data=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();out=OUT/'waiting.mechanism.v2.json'
 if out.exists() and out.read_bytes()!=data:raise ValueError('Frozen waiting v2 bytes changed')
 if not out.exists():out.write_bytes(data)
 print(json.dumps({'sha256':sha(out),'stage_export_allowed':False}))
if __name__=='__main__':main()
