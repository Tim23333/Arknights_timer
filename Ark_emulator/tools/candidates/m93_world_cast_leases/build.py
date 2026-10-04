"""World-wide cast lease exclusivity on the frozen M78 branch."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m78_owned_attachment_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m93_world_cast_leases_candidate'
PIN='27d8ba218d90e6880a4f8704418871a517e5a6f30f034a79db8b04ca46a0cf74'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,before,after):
 p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8');assert s.count(before)==1,(name,before);p.write_text(s.replace(before,after),encoding='utf8',newline='')
def main():
 assert core(BASE)==PIN
 if OUT.exists():raise ValueError('Candidate exists; no overwrite')
 shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 f=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/f).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/f,OUT/f)
 edit('domains/abilities.py',"""    def bind_buff(self, source, cast_id, target, instance):
        if instance is None:
            return
        cast = self._active(source, cast_id)
        if cast is None:
            raise ValueError('Cast-bound buff requires an active owned cast')
        row = {'target': self.ctx.session.world.resolve(target), 'instance': instance}
        for other in self.ctx.get(source, ('runtime', 'casts'), {}).values():
            if other['id'] != cast_id and row in other.get('owned_buffs', []):
                raise ValueError('Buff lease cannot be shared across active casts')
        owned = cast.setdefault('owned_buffs', [])
        if row not in owned:
            owned.append(row)
            self.ctx.set(source, ('runtime', 'casts', cast_id), cast)
""",Path(__file__).with_name('lease_methods.py').read_text(encoding='utf8'))
 edit('domains/effects.py',"""                uid = self.ctx.buffs.apply(source, target, effect["buff"], effect.get("stacks", 1))
                if effect.get("bind_to_cast"):
                    self.ctx.abilities.bind_buff(source, cast.get("id"), target, uid)""","""                if effect.get("bind_to_cast"):
                    self.ctx.abilities.apply_cast_buff(source, cast.get("id"), target, effect["buff"], effect.get("stacks", 1))
                else:
                    self.ctx.buffs.apply(source, target, effect["buff"], effect.get("stacks", 1))""")
 edit('domains/attachments.py',"""        d=self.profile(x);uid=self.ctx.buffs.apply(x['source'],x['target'],d['target_buff'])
        if uid is not None:
            self.ctx.abilities.bind_buff(x['source'],x['cast'],x['target'],uid)""","""        d=self.profile(x);uid=self.ctx.abilities.apply_cast_buff(x['source'],x['cast'],x['target'],d['target_buff'])
        if uid is not None:""")
 report={'parent_core':PIN,'core':core(OUT),'changed':[str(p.relative_to(OUT/'ark_sim')) for p in sorted((OUT/'ark_sim').rglob('*.py')) if sha(p)!=sha(BASE/'ark_sim'/p.relative_to(OUT/'ark_sim'))]}
 target=ROOT/'validation/campaign/m93_world_cast_leases/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
 with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
 print(json.dumps(report))
if __name__=='__main__':main()
