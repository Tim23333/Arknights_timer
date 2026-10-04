"""Integrate independently reviewed rebirth claims with ordered environment."""
import difflib,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
COMMON=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m74_death_claim_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m75_periodic_packets_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m79_rebirth_environment_candidate'
PINS={COMMON:'1ef9635ee70a8159e0523156aeeb177329d19d12a26185b98b9d9fa55ea3c3d5',
      INCOMING:'74ac865eb120c0fd180e096d1e2cc2928d35c7fa0d981e62e77f1e0dafdd90e7',
      BASE:'348c5671adfd73adb501c67a3dd4c51ce4f88228e45dcc6b1026c6eb2822bd57'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def merge(original,desired,current):
    a=original.splitlines(keepends=True);b=desired.splitlines(keepends=True);hunks=[]
    for kind,start,end,ns,ne in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if kind=='equal':continue
        before=''.join(a[start:end]);after=''.join(b[ns:ne]);cursor=end
        if not before.strip() and start>0:
            left=start
            while left>0 and (not before.strip() or current.count(before)>1):
                left-=1;before=a[left]+before;after=a[left]+after
        while not before.strip() or current.count(before)>1:
            if cursor==len(a):
                left=start
                while (not before.strip() or current.count(before)>1) and left>0:
                    left-=1;before=a[left]+before;after=a[left]+after
                if not before.strip() or current.count(before)!=1:raise ValueError('No unique merge context')
                break
            before+=a[cursor];after+=a[cursor];cursor+=1
        if current.count(before)==0:
            if before==after:continue
            raise ValueError('Conflicting merge:'+before[:160])
        current=current.replace(before,after,1);hunks.append({'kind':kind,'start':start,'end':end,'context_end':cursor})
    return current,hunks


def main():
    if OUT.exists():raise ValueError('Candidate exists; preserve it')
    for root,pin in PINS.items():
        if core(root)!=pin:raise ValueError('Frozen core changed')
    changed={};hunks={}
    for p in (INCOMING/'ark_sim').rglob('*.py'):
        name=p.relative_to(INCOMING/'ark_sim');ancestor=COMMON/'ark_sim'/name;current=BASE/'ark_sim'/name
        if ancestor.exists() and p.read_bytes()==ancestor.read_bytes():continue
        if not ancestor.exists():changed[name.as_posix()]=p.read_text(encoding='utf8');continue
        original=ancestor.read_text(encoding='utf8');desired=p.read_text(encoding='utf8');existing=current.read_text(encoding='utf8')
        if name.as_posix()=='content/schemas.py':
            desired=desired.replace('"effects": {"instant_kill",','"effects": {',1)
            desired=desired.replace(', "instant_kill"}', '}',1)
            anchor='"effects": {"no_source_damage",'
            if existing.count(anchor)!=1:raise ValueError('Sourcefree capability field changed')
            existing=existing.replace(anchor,'"effects": {"instant_kill", "no_source_damage",',1)
            original=original.replace('"effects": {','"effects": {"instant_kill", "no_source_damage", ',1)
            desired=desired.replace('"effects": {','"effects": {"instant_kill", "no_source_damage", ',1)
        if name.as_posix()=='domains/lifecycle.py':
            # M72 already introduced exactly these compatible signatures/attribution.
            desired=desired.replace('    def retire(self, ref, reason, *, damage_attribution=None):','    def retire(self, ref, reason):')
            desired=desired.replace('    def _retire(self, ref, reason, *, damage_attribution=None):','    def _retire(self, ref, reason):')
            desired=desired.replace('self._retire(ref, reason, damage_attribution=damage_attribution)','self._retire(ref, reason)')
            desired=desired.replace('self.ctx.emit(event, {"source": ref, "target": ref} if damage_attribution is None else {**damage_attribution, "source": None, "target": ref}, damage_attribution.get("cause") if damage_attribution is not None else None)','self.ctx.emit(event, {"source": ref, "target": ref})')
        try:result,rows=merge(original,desired,existing)
        except ValueError as error:raise ValueError(name.as_posix()+': '+str(error)) from error
        changed[name.as_posix()]=result;hunks[name.as_posix()]=rows
    # Metadata describes capabilities, so preserve both new operation sets.
    name='content/schemas.py';text=changed[name]
    if '"instant_kill"' not in text or '"no_source_damage"' not in text:raise ValueError('Lost supported op')
    name='domains/no_source_damage.py';text=(BASE/'ark_sim'/name).read_text(encoding='utf8')
    before="""            ctx.emit('combat.kill', {**tag, 'target': recipient, 'ability': None, 'cast': None,
                'target_tags': list(ctx.entity(recipient)['tags'])}, damage_event)"""
    after="""            ctx.lifecycle.claim_combat_kill(recipient, {**tag, 'target': recipient, 'ability': None, 'cast': None,
                'target_tags': list(ctx.entity(recipient)['tags'])}, damage_event,
                generation=ctx.get(recipient, ('runtime', 'death_generation')))"""
    if text.count(before)!=1:raise ValueError('No-source final kill source changed')
    changed[name]=text.replace(before,after,1)
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,value in changed.items():(OUT/'ark_sim'/name).write_text(value,encoding='utf8',newline='')
    fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/fixture,OUT/fixture)
    report={'parent_pins':{str(k):v for k,v in PINS.items()},'core':core(OUT),'merge_hunks':hunks,'changed':sorted(changed),
        'status':'constructed; actual tests pending','whole_stage_executed':False}
    out=ROOT/'validation/campaign/m79_rebirth_environment';out.mkdir(parents=True,exist_ok=True);(out/'composition.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'core':report['core'],'changed':report['changed']}))


if __name__=='__main__':main()
