"""Combine source-free field production and verified no-source settlement."""
import difflib,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
COMMON=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m72_no_source_damage_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m62_periodic_fields_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m73_environment_integrated_v2_candidate'
PINS={COMMON:'1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8',BASE:'cbf16097f2fd73b6f4f55eeb0d0f2e2d20a210eec033aac2a6b09996c41f2f86',INCOMING:'a8bee9f99056b3a721c6d12c592104470190cb09e3adeabc001e8e1ba4b78b4d'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def merge(original,incoming,current):
    a=original.splitlines(keepends=True);b=incoming.splitlines(keepends=True);hunks=[]
    for kind,start,end,ns,ne in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if kind=='equal':continue
        before=''.join(a[start:end]);after=''.join(b[ns:ne]);cursor=end
        while not before.strip() or current.count(before)>1:
            if cursor==len(a):raise ValueError('No unique field merge context')
            before+=a[cursor];after+=a[cursor];cursor+=1
        if current.count(before)!=1:raise ValueError('Conflicting field merge context:'+before[:100])
        current=current.replace(before,after,1);hunks.append({'kind':kind,'original_start':start,'original_end':end,'context_end':cursor,'new_start':ns,'new_end':ne})
    return current,hunks


def main():
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    for root,pin in PINS.items():
        if core(root)!=pin:raise ValueError('Frozen field/damage source core changed')
    review=ROOT/'validation/campaign/m72_no_source_damage/verification_final.json'
    if sha(review)!='dd40f43b718f175a99bbf7f9ec50496fd28eda65a6076c45c387eaebc6ec8748':raise ValueError('No-source final review changed')
    writes={};hunks={}
    for p in (INCOMING/'ark_sim').rglob('*'):
        if not p.is_file() or p.suffix not in ('.py','.json'):continue
        rel=p.relative_to(INCOMING/'ark_sim');ancestor=COMMON/'ark_sim'/rel;current=BASE/'ark_sim'/rel
        if ancestor.exists() and ancestor.read_bytes()==p.read_bytes():continue
        if ancestor.exists() and current.exists() and current.read_bytes()!=ancestor.read_bytes():
            if p.suffix!='.py':raise ValueError('Unexpected shared field catalog mutation')
            result,changes=merge(ancestor.read_text(encoding='utf8'),p.read_text(encoding='utf8'),current.read_text(encoding='utf8'));writes[rel.as_posix()]=result.encode();hunks[rel.as_posix()]=changes
        else:writes[rel.as_posix()]=p.read_bytes()
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,raw in writes.items():p=OUT/'ark_sim'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    def edit(name,old,new,count=1):
        p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8')
        if s.count(old)!=count:raise ValueError('Integrated field consumer anchor changed:'+name)
        p.write_text(s.replace(old,new),encoding='utf8',newline='')
    edit('content/capabilities.py',"            require('field.members',scenario['id']+'.periodic_fields',explicit=profile['membership']['rule'])",'''            require('field.members',scenario['id']+'.periodic_fields',explicit=profile['membership']['rule'])
            for index,field_effect in enumerate(profile['effects']):effect(field_effect,scenario['id']+'.periodic_fields.effects['+str(index)+']',[])''')
    edit('domains/periodic_fields.py',"    for effect in p['effects']:\n        if not isinstance(effect,Mapping)","    for effect in p['effects']:\n        from .no_source_damage import validate_request\n        validate_request(effect)\n        if not isinstance(effect,Mapping)")
    # Field origin is data at this specific profile boundary. Other keys named
    # origin (resource IDs, graph inputs) retain their original semantics.
    edit('content/compiler.py','if key == "origin" and value.get("op") == "no_source_damage": continue','if key == "origin" and (value.get("op") == "no_source_damage" or value.get("type") == "periodic_effect_field"): continue',4)
    p=OUT/'ark_sim/content/dependencies.py';s=p.read_text(encoding='utf8')
    before='if name == "origin" and item.get("op") == "no_source_damage":'
    if s.count(before)!=1:raise ValueError('Opaque origin reference anchor changed')
    p.write_text(s.replace(before,'if name == "origin" and (item.get("op") == "no_source_damage" or item.get("type") == "periodic_effect_field"):'),encoding='utf8',newline='')
    offline=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/offline).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/offline,OUT/offline)
    report={'schema':'ark-sim/periodic-source-free-environment-integration/v1','core':core(OUT),'source_cores':{str(p):pin for p,pin in PINS.items()},'merged_hunks':hunks,
        'source_json_sha256':sha(OUT/'ark_sim/rules/contracts.json'),'tested':False,'whole_stage_executed':False,'actual_client_verified':False}
    f=ROOT/'validation/campaign/m73_environment/composition.json';f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))


if __name__=='__main__':main()
