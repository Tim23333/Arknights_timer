"""Refine explicit max1 policy and real rebirth-waiting Aura-only continuity."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';OLD=ROOT.parent/'unpack_work/campaign_shared_aura_v2_candidate';OUT=ROOT.parent/'unpack_work/campaign_shared_aura_v3_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 assert core(BASE)=='d509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1' and core(OLD)=='dfe18ad23d2fe3f936d02d1fafb633d62c7974928e678284714ab89281892776' and not OUT.exists();shutil.copytree(OLD/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 file=OUT/'ark_sim/content/schemas.py';s=file.read_text(encoding='utf8');old="set(p)!={'mode','identity','source_binding','external_child_collision'}";new="set(p)-{'mode','identity','source_binding','external_child_collision','owner_activity'} or not {'mode','identity','source_binding','external_child_collision'}<=set(p)";assert s.count(old)==1;s=s.replace(old,new);s=s.replace("or p['external_child_collision']!='reject':","or p['external_child_collision']!='reject' or p.get('owner_activity','active_only') not in ('active_only','active_or_rebirth_waiting'):");file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/content/compiler.py';s=file.read_text(encoding='utf8');s=s.replace("or policy.get('max_stacks',1)!=1", "or type(policy.get('max_stacks',1)) is not int or policy.get('max_stacks',1)!=1");file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/domains/shared_auras.py';s=file.read_text(encoding='utf8');old=" if not buffs._parent_active(center,parent):return False";new=""" definition=ctx.program.definitions[parent['definition']]
 policy=definition.get('aura',{}).get('lease_policy',{})
 def available(ref):
  if ctx.active(ref):return True
  if policy.get('owner_activity','active_only')!='active_or_rebirth_waiting' or not ctx.alive(ref) or ctx.get(ref,('runtime','state'))!='rebirth':return False
  state=ctx.get(ref,('runtime','rebirth'),{})
  if state.get('phase')!='waiting' or ctx.rebirth is None:return False
  health=ctx.health_resource(ref)
  if ctx.resources.current(ref,health)!=0:return False
  # Before the real finish job is installed only the actual on_begin callback
  # frame authenticates this same source/generation; no cast privilege borrowed.
  if (ref,state.get('generation'),'waiting') in ctx.rebirth._callbacks:return True
  return any(job['id']==state.get('task') and job['kind']=='domain.rebirth.finish' and job['payload'].get('target')==ref and job['payload'].get('generation')==state.get('generation') and job['at']==state.get('due_at') for job in ctx.session.scheduler.pending)
 if not available(center) or not available(parent['source']) or (parent['expires_at'] is not None and ctx.session.time>=parent['expires_at']):return False""";assert s.count(old)==1;s=s.replace(old,new);s=s.replace(" return ctx.aura_available(center) and ctx.aura_available(parent['source'])", " return all(not ctx.route_hidden(ref) or ctx.visibility_policy(ref).get('hidden_auras','suspend')=='retain' for ref in (center,parent['source']))")
 s=s.replace(" return buffs.apply(parent['source'],target,aura['buff'],shared_aura_lease=lease(buffs,center,parent,target,1))", """ uid=buffs.apply(parent['source'],target,aura['buff'],shared_aura_lease=lease(buffs,center,parent,target,1))
 current=next((i for i in buffs._instances(target) if i['id']==uid),None)
 if current is not None and (current['stacks']!=1 or current['expires_at'] is not None):raise ValueError('Shared Aura child actual instance must remain permanent max1')
 return uid""");file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/domains/buffs.py';s=file.read_text(encoding='utf8');old='''                if not self._parent_active(center, parent):
                    self.remove(center, parent["id"], _from_aura=True)''';new='''                parent_available=self._parent_active(center,parent)
                if aura.get('lease_policy'):
                    from .shared_auras import eligible
                    parent_available=eligible(self,center,parent)
                if not parent_available:
                    self.remove(center, parent["id"], _from_aura=True)''';assert s.count(old)==1;s=s.replace(old,new)
 s=s.replace('''                available = self.applicability.active(parent) and self.ctx.aura_available(center) and self.ctx.aura_available(parent["source"])''', '''                available = self.applicability.active(parent) and (parent_available if aura.get('lease_policy') else self.ctx.aura_available(center) and self.ctx.aura_available(parent['source']))''');file.write_text(s,encoding='utf8',newline='');before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};r={'core':core(OUT),'parent_core':core(BASE),'candidate':str(OUT),'changed':[p for p in before if before[p]!=after[p]],'added':sorted(set(after)-set(before)),'parent_guards':before,'candidate_guards':after,'source_waiting_counter':{'path':'packages/campaign/chapter07_boss/patrt/required_waiting_counters/report.json','sha':sha(ROOT/'packages/campaign/chapter07_boss/patrt/required_waiting_counters/report.json')},'waiting_policy_scope':'Only shared Aura lease eligibility for actual authenticated rebirth waiting; no other inactive actor cast/effect/retained projectile privilege','primary_modified':False};out=ROOT/'validation/campaign/shared_aura_v1/composition_v3.json';assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'sha':sha(out)}))
if __name__=='__main__':main()
