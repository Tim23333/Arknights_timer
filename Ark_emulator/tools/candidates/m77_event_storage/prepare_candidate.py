from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m71_event_storage_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m77_event_storage_candidate'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
assert core(BASE)=='15517b90969c61b15340929687092401b4a807b6a3f66d0d2135e780568c04aa'
if not OUT.exists():shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
p=OUT/'ark_sim/kernel/journal.py';b=(BASE/'ark_sim/kernel/journal.py').read_bytes()
b=b.replace(b'from array import array',b'from array import array\nfrom collections.abc import Mapping')
old='''        if reference.get("schema") != cls.SCHEMA:
            raise ValueError("Unsupported event journal reference")
        path = Path(reference["path"])'''
new='''        if (not isinstance(reference, Mapping) or set(reference)!={'schema','path','sha256','bytes','count'}
                or reference.get('schema') != cls.SCHEMA):
            raise ValueError("Unsupported event journal reference fields/schema")
        for key in ('bytes','count'):
            if type(reference[key]) is not int or reference[key] < 0:
                raise ValueError('Event journal reference '+key+' must be a nonnegative integer')
        digest_value=reference['sha256']
        if type(digest_value) is not str or len(digest_value)!=64 or any(c not in '0123456789abcdef' for c in digest_value):
            raise ValueError('Event journal reference SHA256 must be canonical lowercase hex')
        if type(reference['path']) is not str or not reference['path']:
            raise ValueError('Event journal reference path must be nonempty absolute string')
        path = Path(reference["path"])'''
a=old.encode();c=new.encode()
if b'\r\n' in b:a=a.replace(b'\n',b'\r\n');c=c.replace(b'\n',b'\r\n')
assert b.count(a)==1;b=b.replace(a,c);p.write_bytes(b)
print(json.dumps({'root':str(OUT),'core':core(OUT),'files':['kernel/journal.py']}))
