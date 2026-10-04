from pathlib import Path
import shutil,hashlib
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m76_death_projectiles_v7_candidate';DEST=ROOT.parent/'unpack_work/campaign_m85_death_sequence_candidate'
def main():
 if DEST.exists():raise ValueError('New candidate only; never rewrite frozen roots')
 shutil.copytree(BASE/'ark_sim',DEST/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 p=DEST/'ark_sim/domains/death_projectiles.py';s=p.read_text(encoding='utf8');old="def emit(ctx,ref):\n    for spec in ctx.get(ref,('lifecycle','death_projectiles'),[]):\n        validate(spec)";new="""def emit(ctx,ref):
    # Optional actual death epoch supports future rebirth integration without
    # inventing a generation on legacy actors. Identity is the canonical ref.
    ref=ctx.session.world.resolve(ref)
    generation=ctx.get(ref,('runtime','death_generation'))
    def current():
        return (ctx.active(ref) and not ctx.state().get('finished',False)
            and ctx.get(ref,('runtime','death_generation'))==generation)
    for spec in ctx.get(ref,('lifecycle','death_projectiles'),[]):
        if not current():return
        validate(spec)"""
 if old not in s:raise ValueError('Frozen source context mismatch')
 s=s.replace(old,new,1);s=s.replace("        if type(accepted) is not bool:raise ValueError('death emission decision must be strict boolean')", "        if type(accepted) is not bool:raise ValueError('death emission decision must be strict boolean')\n        if not current():return",1);p.write_text(s,encoding='utf8')
 print(hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':main()
