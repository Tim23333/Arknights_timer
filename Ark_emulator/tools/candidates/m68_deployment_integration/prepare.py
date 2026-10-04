"""Combine reviewed cooldown strategy and final connectivity branch."""
import difflib,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
COMMON=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m69_connectivity_plain_deploy_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m63_deploy_cooldown_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'
PINS={COMMON:'1ef9635ee70a8159e0523156aeeb177329d19d12a26185b98b9d9fa55ea3c3d5',
      BASE:'5afc1e7df9008a5d4c6515ca552d4a0d1ee1635a70b36d88a2b859b572e39aae',
      INCOMING:'b5263988e3ed9c448514ce1fe67ad64504f25d2565061cdafe5f262e94a32ac6'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def merge(original,desired,current):
    a=original.splitlines(keepends=True);b=desired.splitlines(keepends=True);edits=[]
    for kind,start,end,ns,ne in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if kind=='equal':continue
        before=''.join(a[start:end]);after=''.join(b[ns:ne])
        if not before.strip():
            cursor=end
            while cursor<len(a) and not a[cursor].strip():cursor+=1
            if cursor==len(a):raise ValueError('Unanchored EOF insertion')
            tail=''.join(a[end:cursor+1]);before=before+tail;after=after+tail
        if current.count(before)!=1:raise ValueError('Nonunique cooldown merge anchor:'+before[:80])
        current=current.replace(before,after,1);edits.append({'kind':kind,'original_start':start,'original_end':end,'new_start':ns,'new_end':ne})
    return current,edits


def main():
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    for root,pin in PINS.items():
        if core(root)!=pin:raise ValueError('Frozen source core changed')
    review=ROOT/'validation/campaign/m63_deploy_cooldown/final.json'
    if sha(review)!='a5d0ea9777594cea80d386c70f4dd0f976338056921236d94a96788be6a11581':raise ValueError('Cooldown review drift')
    edits={};changed={}
    # Prepare every merge in memory before creating any checkout.
    for p in (INCOMING/'ark_sim').rglob('*.py'):
        rel=p.relative_to(INCOMING/'ark_sim');ancestor=COMMON/'ark_sim'/rel
        if p.read_bytes()==ancestor.read_bytes():continue
        name=rel.as_posix()
        if name not in {'content/schemas.py','content/compiler.py','domains/deployment.py','domains/lifecycle.py'}:raise ValueError('Unexpected cooldown branch file')
        original=ancestor.read_text(encoding='utf8');desired=p.read_text(encoding='utf8');current=(BASE/'ark_sim'/rel).read_text(encoding='utf8')
        if name=='content/schemas.py':
            # Both branches deliberately extend the same explicit field set.
            desired=desired.replace('"deployable": {"cooldown_start", "stock",','"deployable": {"stock",',1)
            if current.count('"deployable": {"connectivity", "stock",')!=1:raise ValueError('Connectivity schema field set changed')
            current=current.replace('"deployable": {"connectivity", "stock",','"deployable": {"connectivity", "cooldown_start", "stock",',1)
        result,hunks=merge(original,desired,current)
        if name=='domains/deployment.py':
            # Reserve before a new opt-in connectivity calculation can invoke
            # a legal nested record callback. Defaults remain unchanged.
            block="""    start=cooldown_start(plan['deployable'])
    # World reservation rolls back together with payments and rule effects.
    if start=='deploy':context.set(ref,('runtime','deployment_recorded'),True)
"""
            if result.count(block)!=1:raise ValueError('Cooldown record reservation anchor changed')
            result=result.replace(block,'',1)
            anchor='    from .deploy_connectivity import inspect as inspect_connectivity\n    inspect_connectivity(context,context.program.definitions'
            replacement="""    start=cooldown_start(plan['deployable'])
    if start=='deploy' or 'connectivity' in plan['deployable']:
        context.set(ref,('runtime','deployment_recorded'),True)
    from .deploy_connectivity import inspect as inspect_connectivity
    inspect_connectivity(context,context.program.definitions"""
            if result.count(anchor)!=1:raise ValueError('Connectivity record anchor changed')
            result=result.replace(anchor,replacement,1)
        edits[name]=hunks;changed[name]=result
    if set(changed)!={'content/schemas.py','content/compiler.py','domains/deployment.py','domains/lifecycle.py'}:raise ValueError('Cooldown source change set differs')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,value in changed.items():(OUT/'ark_sim'/name).write_text(value,encoding='utf8',newline='')
    # Only a frozen offline JSON asset, never V1 executable code.
    p=COMMON/'ark_emulator/levels/packs/level_main_00-01.json';dest=OUT/'ark_emulator/levels/packs/level_main_00-01.json';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    report={'schema':'ark-sim/deployment-connectivity-cooldown-integration/v1','core':core(OUT),'source_cores':{str(p):pin for p,pin in PINS.items()},
        'merged_hunks':edits,'changed_files':{name:sha(OUT/'ark_sim'/name) for name in changed},'tested':False,'actual_client_verified':False}
    f=ROOT/'validation/campaign/m68_integration/composition.json';f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps({'core':report['core'],'merged_files':list(changed)}))


if __name__=='__main__':main()
