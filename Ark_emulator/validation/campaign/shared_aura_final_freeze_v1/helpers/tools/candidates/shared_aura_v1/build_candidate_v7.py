"""Only authenticated Aura source qualification; typed targets/hidden paths unchanged."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';OLD=ROOT.parent/'unpack_work/campaign_shared_aura_v6_candidate';OUT=ROOT.parent/'unpack_work/campaign_shared_aura_v7_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 assert core(OLD)=='f519c82f652b2662f7f5f4a9009bb19a650a266ea009f98ca9301b200374c3fb' and not OUT.exists();shutil.copytree(OLD/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));file=OUT/'ark_sim/domains/movement.py';s=file.read_text(encoding='utf8');s=s.replace('def qualifies(self, source, candidate, selector, ability=None, effect=None, observable=False):','def qualifies(self, source, candidate, selector, ability=None, effect=None, observable=False, *, aura_parent=None):');s=s.replace('def select(self, source, selector_id, ability=None, effect=None, primary=None):','def select(self, source, selector_id, ability=None, effect=None, primary=None, *, aura_parent=None):');old='''        if not self.ctx.active(source) or not self.ctx.active(candidate) or self.ctx.route_hidden(source) or self.ctx.route_hidden(candidate):
            return False''';new='''        source_allowed=self.ctx.active(source)
        if aura_parent is not None:
            from .shared_auras import selection_source_allowed
            source_allowed=selection_source_allowed(self.ctx,source,selector,aura_parent)
        if not source_allowed or not self.ctx.active(candidate) or self.ctx.route_hidden(source) or self.ctx.route_hidden(candidate):
            return False''';assert s.count(old)==1;s=s.replace(old,new);s=s.replace('self.qualifies(source, ref, definition, ability, effect, observable=True)','self.qualifies(source, ref, definition, ability, effect, observable=True, aura_parent=aura_parent)');old='''        definition, entity, candidates = self._candidate_input(source, selector_id, primary)''';new=old+'''
        if aura_parent is not None:
            from .shared_auras import selection_source_allowed
            if not selection_source_allowed(self.ctx,source,definition,aura_parent):raise ValueError('Aura source selection requires a current authorized parent/selector')''';assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/domains/shared_auras.py';s=file.read_text(encoding='utf8');s+='''
def selection_source_allowed(ctx,source,selector,parent_uid):
 if type(parent_uid) is not str or not parent_uid:raise ValueError('Aura source selection parent requires actual UID string')
 source=ctx.session.world.resolve(source)
 parent=ctx.buffs._live_parent(source,parent_uid)
 if parent is None:return False
 definition=ctx.program.definitions[parent['definition']]
 aura=definition.get('aura',{})
 if not aura.get('lease_policy') or aura.get('selector')!=selector.get('id'):return False
 return eligible(ctx.buffs,source,parent)
''';s=s.replace("ctx.spatial.select(row['center'],aura['selector'])", "ctx.spatial.select(row['center'],aura['selector'],aura_parent=parent['id'])");file.write_text(s,encoding='utf8',newline='')
 file=OUT/'ark_sim/domains/buffs.py';s=file.read_text(encoding='utf8');old='''                desired = set(self.ctx.spatial.select(center, aura["selector"])) if available else set()''';new='''                desired = set(self.ctx.spatial.select(center, aura['selector'],aura_parent=parent['id'])) if available and aura.get('lease_policy') else set(self.ctx.spatial.select(center,aura['selector'])) if available else set()''';assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='');before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};r={'core':core(OUT),'parent_core':core(BASE),'candidate':str(OUT),'changed':[p for p in before if before[p]!=after[p]],'added':sorted(set(after)-set(before)),'parent_guards':before,'candidate_guards':after,'primary_modified':False,'no_fake_active_source':True,'no_cast_projectile_permission_borrowed':True};out=ROOT/'validation/campaign/shared_aura_v1/composition_v7.json';assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'sha':sha(out)}))
if __name__=='__main__':main()
