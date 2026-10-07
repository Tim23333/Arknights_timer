"""Opt-in shared Aura candidate from immutable d509; legacy independent semantics preserved."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';OUT=ROOT.parent/'unpack_work/campaign_shared_aura_v1_candidate';PARENT='d509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 assert core(BASE)==PARENT and not OUT.exists();before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));shutil.copyfile(Path(__file__).with_name('shared_auras_impl_v1.py'),OUT/'ark_sim/domains/shared_auras.py')
 file=OUT/'ark_sim/content/schemas.py';s=file.read_text(encoding='utf8');s=s.replace('fields(aura, {"selector", "buff"},','fields(aura, {"selector", "buff", "lease_policy"},');old='''            if not all(isinstance(aura.get(key), str) and aura[key].strip() for key in ("selector", "buff")):
                raise ContentError(f"{identifier}.aura: selector and buff references are required")''';new=old+'''
            if 'lease_policy' in aura:
                p=aura['lease_policy']
                if not isinstance(p,Mapping) or set(p)!={'mode','identity','source_binding','external_child_collision'} or p['mode']!='shared' or p['identity']!=['definition','target'] or p['source_binding']!='oldest_live_lease' or p['external_child_collision']!='reject':
                    raise ContentError(f"{identifier}.aura: explicit shared lease policy required")''';assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/content/compiler.py';s=file.read_text(encoding='utf8');old='''                if member.get("stacking", {}).get("mode") != "independent":
                    raise CompileError(f"{identifier}.aura: member requires independent stacking")''';new='''                if definition['aura'].get('lease_policy'):
                    policy=member.get('stacking',{})
                    if policy.get('mode','refresh')!='refresh' or policy.get('max_stacks',1)!=1 or policy.get('policy') or ('duration_seconds' in member.get('parameters',{}) and member['parameters']['duration_seconds']!=0):
                        raise CompileError(f"{identifier}.aura: shared child must be nonstacking permanent refresh max1")
                elif member.get("stacking", {}).get("mode") != "independent":
                    raise CompileError(f"{identifier}.aura: member requires independent stacking")''';assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/domains/buffs.py';s=file.read_text(encoding='utf8');s=s.replace('duration_override=None):','duration_override=None, shared_aura_lease=None):',1);old='''            policy = definition.get("stacking", {})''';new='''            if shared_aura_lease is None and any(i['definition']==buff_id and i.get('aura_leases') for i in self._instances(target)):
                raise ValueError('External application collides with a shared Aura child')
            if shared_aura_lease is not None:
                from .shared_auras import validate_acquisition
                validate_acquisition(self, source, target, buff_id, shared_aura_lease)
            policy = definition.get("stacking", {})''';assert s.count(old)==1;s=s.replace(old,new);old='''            if aura_parent is not None:
                instance["aura_parent"] = aura_parent''';new=old+'''
            if shared_aura_lease is not None:
                instance['aura_leases']={shared_aura_lease['parent']:shared_aura_lease}
                instance['aura_next_lease_order']=2''';assert s.count(old)==1;s=s.replace(old,new)
 old='''                    self.remove(int(member), child, _from_aura=True)''';new='''                    if self.ctx.program.definitions[item['definition']].get('aura',{}).get('lease_policy'):
                        from .shared_auras import release
                        release(self, int(member), child, item['id'])
                    else:self.remove(int(member), child, _from_aura=True)''';assert s.count(old)==1;s=s.replace(old,new)
 old='''                if child.get("aura_parent") == parent_id:
                    self.remove(entity["id"], child["id"], _from_aura=True)''';new=old+'''
                elif parent_id in child.get('aura_leases',{}):
                    from .shared_auras import release
                    release(self,entity['id'],child['id'],parent_id)''';assert s.count(old)==1;s=s.replace(old,new)
 s=s.replace('if child.get("aura_parent") == parent_id:\n                    key = str(entity["id"])','if child.get("aura_parent") == parent_id or parent_id in child.get("aura_leases",{}):\n                    key = str(entity["id"])',1)
 old='''                invalid = False
                for member, child in list(members.items()):''';new='''                invalid = False
                if aura.get('lease_policy'):
                    from .shared_auras import reconcile_parent
                    reconcile_parent(self,center,parent,desired)
                    continue
                for member, child in list(members.items()):''';assert s.count(old)==1;s=s.replace(old,new)
 old='''    def reconcile(self, session=None):
        self.applicability.reconcile()''';new='''    def reconcile(self, session=None):
        if self.has_auras:
            from .shared_auras import prune
            prune(self)
        self.applicability.reconcile()''';assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='');after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};changed=[p for p in before if before[p]!=after[p]];assert set(changed)=={'ark_sim/content/schemas.py','ark_sim/content/compiler.py','ark_sim/domains/buffs.py'};assert set(after)-set(before)=={'ark_sim/domains/shared_auras.py'};r={'core':core(OUT),'parent_core':PARENT,'candidate':str(OUT),'changed':changed,'added':['ark_sim/domains/shared_auras.py'],'parent_guards':before,'candidate_guards':after,'source_marker_unchanged':True,'HP0_waiting_implemented':False,'primary_modified':False};out=ROOT/'validation/campaign/shared_aura_v1/composition.json';assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'sha':sha(out)}))
if __name__=='__main__':main()
