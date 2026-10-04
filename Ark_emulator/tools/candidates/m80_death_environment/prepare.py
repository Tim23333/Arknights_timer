"""Compose source-bound postmortem projectile capability with M79."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.candidates.m79_rebirth_environment.prepare import merge,core,sha
COMMON=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m76_death_projectiles_v7_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m79_rebirth_environment_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m80_death_environment_candidate'
PINS={COMMON:'1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8',
      INCOMING:'67028cc91fe55931a62c19d29c8a04dcc4bc6c354b059b1acaac1982733147ad',
      BASE:'2e734d6a58b825cecfd85966d49a62de33281131c78b59c3764ba296a7466ef3'}


def main():
    if OUT.exists():raise ValueError('Candidate exists; preserve it')
    for root,pin in PINS.items():
        if core(root)!=pin:raise ValueError('Parent core changed')
    writes={};hunks={}
    for p in (INCOMING/'ark_sim').rglob('*.py'):
        rel=p.relative_to(INCOMING/'ark_sim');ancestor=COMMON/'ark_sim'/rel;current=BASE/'ark_sim'/rel
        if ancestor.exists() and p.read_bytes()==ancestor.read_bytes():continue
        if not ancestor.exists():writes[rel.as_posix()]=p.read_text(encoding='utf8');continue
        a=ancestor.read_text(encoding='utf8');b=p.read_text(encoding='utf8');c=current.read_text(encoding='utf8')
        if rel.as_posix()=='domains/resources.py':
            # Keep M74 rebirth/direct-zero transaction and M72 attribution
            # kwargs; death emission adds one opt-in condition to its wrapper.
            start=b.index('    def adjust(');end=b.index('    def _commit_change(',start)
            parent_start=a.index('    def adjust(');parent_end=a.index('    def _commit_change(',parent_start)
            b=b[:start]+a[parent_start:parent_end]+b[end:]
            anchor='        if rebirth is not None and (self.ctx.get(canonical,("rebirth",)) is not None or canonical in rebirth._requests):'
            if c.count(anchor)!=1:raise ValueError('Rebirth adjustment wrapper changed')
            c=c.replace(anchor,'        if self.ctx.get(canonical,("lifecycle","death_projectiles")) or (rebirth is not None and (self.ctx.get(canonical,("rebirth",)) is not None or canonical in rebirth._requests)):',1)
        if rel.as_posix()=='domains/lifecycle.py':
            # Both branches change the opt-in retirement wrapper. M72 kwargs
            # remain; only add the emission condition here.
            old='        if self.ctx.terrain is None:\n            return self._retire(ref, reason)'
            new="        if self.ctx.terrain is None and not self.ctx.get(ref,('lifecycle','death_projectiles')):\n            return self._retire(ref, reason)"
            b=b.replace(new,old,1)
            anchor='        if self.ctx.terrain is None:\n            return self._retire(ref, reason, damage_attribution=damage_attribution)'
            if c.count(anchor)!=1:raise ValueError('Attribution retirement wrapper changed')
            c=c.replace(anchor,'        if self.ctx.terrain is None and not self.ctx.get(ref,("lifecycle","death_projectiles")):\n            return self._retire(ref, reason, damage_attribution=damage_attribution)',1)
        try:result,rows=merge(a,b,c)
        except ValueError as error:raise ValueError(rel.as_posix()+': '+str(error)) from error
        if rel.as_posix()=='domains/lifecycle.py':
            # Only after a reentrant emission completes may actual death take
            # a generation; nested rejected retirement never allocates one.
            generation="""        if reason == 'dead':
            generation=self.ctx.get(ref,('runtime','death_generation'),0)+1
            self.ctx.set(ref,('runtime','death_generation'),generation)
"""
            if result.count(generation)!=1:raise ValueError('Death generation anchor changed')
            result=result.replace(generation,'',1)
            marker='        self.ctx.set(ref, ("runtime", "alive"), False)'
            if result.count(marker)!=1:raise ValueError('Death commit anchor changed')
            result=result.replace(marker,generation+marker,1)
        writes[rel.as_posix()]=result;hunks[rel.as_posix()]=rows
    catalog=json.loads((BASE/'ark_sim/rules/contracts.json').read_bytes());incoming=json.loads((INCOMING/'ark_sim/rules/contracts.json').read_bytes())
    rows=[r for r in incoming['contracts'] if r['id']=='lifecycle.death_emission'];assert len(rows)==1
    catalog['contracts'].extend(rows)
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,value in writes.items():(OUT/'ark_sim'/name).write_text(value,encoding='utf8',newline='')
    (OUT/'ark_sim/rules/contracts.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/fixture,OUT/fixture)
    report={'core':core(OUT),'parent_pins':{str(k):v for k,v in PINS.items()},'hunks':hunks,'changed':sorted(writes),
        'scope':'Unverified M80 composition; M76 independent peer still pending; no production promotion or stage receipt'}
    out=ROOT/'validation/campaign/m80_death_environment';out.mkdir(parents=True,exist_ok=True);(out/'composition.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'core':report['core'],'changed':report['changed']}))


if __name__=='__main__':main()
