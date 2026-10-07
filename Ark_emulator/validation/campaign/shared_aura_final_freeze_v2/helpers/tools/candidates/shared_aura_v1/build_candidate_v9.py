"""Authenticated retained waiting owner can remain its own Aura target, no other waiting actor."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';OLD=ROOT.parent/'unpack_work/campaign_shared_aura_v8_candidate';OUT=ROOT.parent/'unpack_work/campaign_shared_aura_v9_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 assert core(OLD)=='f5923e9b4d9c438fe5d7cf8ece0565a9d3998584c1163f93589660ff0aa99085' and not OUT.exists();shutil.copytree(OLD/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));file=OUT/'ark_sim/domains/shared_auras.py';s=file.read_text(encoding='utf8');s+='''
def target_allowed(buffs,center,parent,target):
 ctx=buffs.ctx
 if ctx.active(target):return True
 return (target==center and ctx.alive(target) and eligible(buffs,center,parent)
     and ctx.program.definitions[parent['definition']].get('aura',{}).get('lease_policy',{}).get('owner_activity')=='active_or_rebirth_waiting'
     and ctx.rebirth is not None and ctx.rebirth.aura_waiting_parent_available(target,parent))
def selection_target_allowed(ctx,source,candidate,selector,parent_uid):
 if ctx.active(candidate):return True
 source=ctx.session.world.resolve(source);candidate=ctx.session.world.resolve(candidate)
 if candidate!=source or not selection_source_allowed(ctx,source,selector,parent_uid):return False
 parent=ctx.buffs._live_parent(source,parent_uid)
 return parent is not None and target_allowed(ctx.buffs,source,parent,candidate)
def retained_waiting_self_child(buffs,target,child):
 current=next((i for i in buffs._instances(target) if i['id']==child['id'] and i['generation']==child['generation']),None)
 if current is None:return False
 for uid,row in current.get('aura_leases',{}).items():
  if row['center']!=target:continue
  parent=buffs._live_parent(target,uid)
  if parent is not None and target_allowed(buffs,target,parent,target):return True
 return False
''';s=s.replace("or not buffs.ctx.active(target):continue", "or not target_allowed(buffs,row['center'],parent,target):continue");s=s.replace("  if not buffs.ctx.active(member):continue", "  if not target_allowed(buffs,center,current,member):continue");file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/domains/movement.py';s=file.read_text(encoding='utf8');s=s.replace('def _candidate_input(self, source, selector_id, primary=None):','def _candidate_input(self, source, selector_id, primary=None, *, aura_parent=None):');s=s.replace('''        if not source_allowed or not self.ctx.active(candidate) or self.ctx.route_hidden(source) or self.ctx.route_hidden(candidate):''','''        candidate_allowed=self.ctx.active(candidate)
        if aura_parent is not None and not candidate_allowed:
            from .shared_auras import selection_target_allowed
            candidate_allowed=selection_target_allowed(self.ctx,source,candidate,selector,aura_parent)
        if not source_allowed or not candidate_allowed or self.ctx.route_hidden(source) or self.ctx.route_hidden(candidate):''');old='''        entity = self.ctx.entity(source)
        candidates =''';new='''        entity = self.ctx.entity(source)
        def active_or_aura_self(ref):
            if self.ctx.get(ref,('runtime','active'),True):return True
            if aura_parent is None:return False
            from .shared_auras import selection_target_allowed
            return selection_target_allowed(self.ctx,source,ref,definition,aura_parent)
        candidates =''';assert s.count(old)==1;s=s.replace(old,new);s=s.replace('and self.ctx.get(e["id"], (\'runtime\', \'active\'), True) and not self.ctx.route_hidden(e["id"])]','and active_or_aura_self(e["id"]) and not self.ctx.route_hidden(e["id"])]');s=s.replace('''                candidates = [e for e in candidates if getattr(self.ctx, 'active', self.ctx.alive)(e["id"])]''','''                candidates = [e for e in candidates if active_or_aura_self(e['id'])]''');old='''    def select(self, source, selector_id, ability=None, effect=None, primary=None, *, aura_parent=None):
        definition, entity, candidates = self._candidate_input(source, selector_id, primary)''';new=old.replace('primary)','primary,aura_parent=aura_parent)');assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/domains/buffs.py';s=file.read_text(encoding='utf8');old='''                desired = {ref for ref in desired if getattr(self.ctx, 'active', self.ctx.alive)(ref)}''';new='''                if aura.get('lease_policy'):
                    from .shared_auras import target_allowed
                    desired={ref for ref in desired if target_allowed(self,center,parent,ref)}
                else:desired = {ref for ref in desired if getattr(self.ctx, 'active', self.ctx.alive)(ref)}''';assert s.count(old)==1;s=s.replace(old,new);old='''                    if not retained:self.remove(target, instance["id"])''';new='''                    if not retained and instance.get('aura_leases'):
                        from .shared_auras import retained_waiting_self_child
                        retained=retained_waiting_self_child(self,target,instance)
                    if not retained:self.remove(target, instance["id"])''';assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/domains/rebirth.py';s=file.read_text(encoding='utf8');old="""     if instance['definition'] not in spec.get('retain_buffs',[]):self.ctx.buffs.remove(ref,instance['id'])""";new="""     if instance['definition'] not in spec.get('retain_buffs',[]):
      from .shared_auras import retained_waiting_self_child
      if not retained_waiting_self_child(self.ctx.buffs,ref,instance):self.ctx.buffs.remove(ref,instance['id'])""";assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='');before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};r={'core':core(OUT),'parent_core':core(BASE),'candidate':str(OUT),'changed':[p for p in before if before[p]!=after[p]],'added':sorted(set(after)-set(before)),'parent_guards':before,'candidate_guards':after,'primary_modified':False,'waiting_target_scope':'Only candidate==Aura center with same actual authenticated retained waiting parent; not other inactive targets or general cast/selection permissions.'};out=ROOT/'validation/campaign/shared_aura_v1/composition_v9.json';assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'sha':sha(out)}))
if __name__=='__main__':main()
