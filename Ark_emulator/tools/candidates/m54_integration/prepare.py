"""Apply frozen qualified-area changes without dropping visibility filtering."""
import difflib,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
COMMON=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m52_visibility_stock_integrated_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m53_qualified_area_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m54_qualified_visibility_candidate'
PINS={COMMON:'a829685336bc55af4d5b3098f6eca9887ce870906ab20429ec43de789630fbc9',BASE:'bfbd9613dc36f2ac39c91381f57e8e4f7d306386514843d8b83ea020e45580fe',INCOMING:'5ed2a57028755f6781bccfbc6845ad62fd841f5d96d55f1d49cdc973acace047'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def merge_text(ancestor,incoming,current):
    original=ancestor.splitlines(keepends=True);desired=incoming.splitlines(keepends=True);result=current
    edits=[]
    for tag,a,b,c,d in difflib.SequenceMatcher(None,original,desired,autojunk=False).get_opcodes():
        if tag=='equal':continue
        before=''.join(original[a:b]);after=''.join(desired[c:d])
        if not before:
            # The preceding candidate-filter line is independently extended by
            # visibility. Anchor on the unchanged next dispatch line instead.
            before=original[a];after=after+before
        if result.count(before)!=1:raise ValueError('Reviewed qualified-area merge hunk is not unique in current branch')
        result=result.replace(before,after,1);edits.append({'ancestor_start':a,'ancestor_end':b,'new_start':c,'new_end':d,'kind':tag})
    return result,edits


def main():
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    for root,pin in PINS.items():
        if core(root)!=pin:raise ValueError('Frozen core drift')
    report=ROOT/'validation/campaign/m53_qualified_area/candidate_final.json'
    if sha(report)!='1542a1e852b28cab2bea31589903319b0325e216722d2003ebdae450ce655c52':raise ValueError('Frozen qualified report drift')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    changes={};merged={}
    for path in sorted((INCOMING/'ark_sim').rglob('*.py')):
        relative=path.relative_to(INCOMING/'ark_sim');old=COMMON/'ark_sim'/relative;current=BASE/'ark_sim'/relative;target=OUT/'ark_sim'/relative
        if old.exists() and path.read_bytes()==old.read_bytes():continue
        if old.exists() and current.exists() and current.read_bytes()!=old.read_bytes():
            text,edits=merge_text(old.read_text(encoding='utf8'),path.read_text(encoding='utf8'),current.read_text(encoding='utf8'));target.write_text(text,encoding='utf8',newline='');merged[relative.as_posix()]=edits
        else:target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        changes[relative.as_posix()]=sha(target)
    if set(merged)!={'content/capabilities.py','domains/effects.py'}:raise ValueError('Unexpected qualifiedarea overlapping files')
    # Both runtime predicates must survive the explicit overlapping merge.
    effects=(OUT/'ark_sim/domains/effects.py').read_text()
    if 'self.ctx.spatial.available' not in effects or 'area_selection_states' not in effects:raise ValueError('Area visibility or source qualification lost in merge')
    result={'schema':'ark-sim/qualified-visibility-integration/v1','core':core(OUT),'source_cores':{str(k):v for k,v in PINS.items()},'changed_files':changes,'merged_hunks':merged,'tested':False,'client_verified':False}
    out=ROOT/'validation/campaign/m54_integration/composition.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps({'core':result['core'],'merged_files':list(merged)}))


if __name__=='__main__':main()
