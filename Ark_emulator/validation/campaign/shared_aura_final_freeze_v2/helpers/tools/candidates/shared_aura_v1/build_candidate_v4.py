"""Real consume-transition authentication; no early scheduling or casting privilege."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';OLD=ROOT.parent/'unpack_work/campaign_shared_aura_v3_candidate';OUT=ROOT.parent/'unpack_work/campaign_shared_aura_v4_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 assert core(OLD)=='d5bcdfdc993c2929f04ea05ce409c1a55803e77ffc8a54daa96173bb3dc4491c' and not OUT.exists();shutil.copytree(OLD/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));file=OUT/'ark_sim/domains/rebirth.py';s=file.read_text(encoding='utf8');s=s.replace('self._callbacks=[];self._settling=False','self._callbacks=[];self._settling=False;self._aura_waiting_begins=[]',1);old=' def consume(self,ref,event):';new=''' def aura_waiting_parent_available(self,ref,parent):
  if not self.ctx.alive(ref) or self.ctx.state().get('finished') or self._state(ref).get('phase')!='waiting':return False
  spec=self._spec(ref)
  if not spec or self.ctx.resources.current(ref,spec['resource'])!=0 or parent.get('target')!=ref or parent['definition'] not in spec.get('retain_buffs',[]):return False
  current=next((i for i in self.ctx.buffs._instances(ref) if i['id']==parent['id']),None)
  if current is None or current['generation']!=parent['generation'] or current['source']!=parent['source']:return False
  for frame in reversed(self._aura_waiting_begins):
   row=frame['parents'].get(parent['id'])
   if frame['actor']==ref and frame['generation']==self._state(ref).get('generation') and row and row['definition']==parent['definition'] and row['target']==ref and row['source']==parent['source'] and row['generation']<=parent['generation']:return True
  state=self._state(ref)
  return any(job['id']==state.get('task') and job['kind']=='domain.rebirth.finish' and job['payload'].get('target')==ref and job['payload'].get('generation')==state.get('generation') and job['at']==state.get('due_at') for job in self.ctx.session.scheduler.pending)
 def consume(self,ref,event):
  spec=self._spec(ref) or {};retained=set(spec.get('retain_buffs',[]))
  frame={'actor':ref,'generation':self._state(ref).get('generation',0)+1,'parents':{i['id']:{k:i[k] for k in ('definition','target','source','generation')} for i in self.ctx.buffs._instances(ref) if i['definition'] in retained}}
  self._aura_waiting_begins.append(frame)
  try:return self._consume(ref,event)
  finally:self._aura_waiting_begins.pop()
 def _consume(self,ref,event):''';assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/domains/shared_auras.py';s=file.read_text(encoding='utf8');old="""  # Before the real finish job is installed only the actual on_begin callback
  # frame authenticates this same source/generation; no cast privilege borrowed.
  if (ref,state.get('generation'),'waiting') in ctx.rebirth._callbacks:return True
  return any(job['id']==state.get('task') and job['kind']=='domain.rebirth.finish' and job['payload'].get('target')==ref and job['payload'].get('generation')==state.get('generation') and job['at']==state.get('due_at') for job in ctx.session.scheduler.pending)""";new="""  # Actual retained parent identity is authenticated by the real consume
  # transition or already-installed finish job. World flags alone never grant it.
  return ctx.rebirth.aura_waiting_parent_available(ref,parent)""";assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='');before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};r={'core':core(OUT),'parent_core':core(BASE),'candidate':str(OUT),'changed':[p for p in before if before[p]!=after[p]],'added':sorted(set(after)-set(before)),'parent_guards':before,'candidate_guards':after,'waiting_auth':'Real consume actor/generation/internal retained parent handle context, finally cleared; or actual same-gen finish job. HP0/aliveTrue/phasewaiting/nonterminal and actual parent preserved, no actor cast/projectile privileges.','primary_modified':False};out=ROOT/'validation/campaign/shared_aura_v1/composition_v4.json';assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'sha':sha(out)}))
if __name__=='__main__':main()
