"""Apply only reviewed C6 deltas to the frozen current generic core."""
import ast,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/primary_frost_v5_before_chapter05_v3_promotion'
LEFT=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate'
RIGHT=ROOT.parent/'unpack_work/campaign_buff_application_v7_candidate'
OUT=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v2_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def identity(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def main():
    assert identity(BASE)=='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
    assert identity(LEFT)=='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
    assert identity(RIGHT)=='4ef955c5d5a7628382fc3d15003bb0a30c749832d210ca50897355568ec8d329'
    diff=json.loads((ROOT/'packages/campaign/chapter06_cold/candidate.diff.json').read_bytes())
    assert len(diff['changes'])==6 and not OUT.exists()
    guards={str(p):sha(p) for folder in [BASE,LEFT,RIGHT] for p in (folder/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'}}
    shutil.copytree(LEFT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    changes=[]
    for change in diff['changes']:
        rel=Path(change['path']);dest=OUT/rel;right=RIGHT/rel;base=BASE/rel
        assert sha(right)==change['candidate_sha256']
        if change['base_sha256'] is None:
            assert not dest.exists();shutil.copyfile(right,dest)
        elif rel.suffix=='.json':
            b,l,r=[json.loads(p.read_bytes()) for p in [base,LEFT/rel,right]]
            assert b['version']==l['version']==r['version']
            new={c['id']:c for c in r['contracts'] if c not in b['contracts']}
            assert set(new)=={'buff.application'} and r['contracts']==b['contracts']+list(new.values())
            assert all(c['id'] not in {x['id'] for x in l['contracts']} for c in new.values())
            l['contracts']+=list(new.values());dest.write_text(json.dumps(l,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
        else:
            # Git's three-way merge keeps unrelated 8fa changes and reports conflicts.
            assert sha(base)==change['base_sha256']
            if rel.as_posix()=='ark_sim/content/schemas.py':
                texts=[path.read_text(encoding='utf8') for path in [base,LEFT/rel,right]]
                for key in ['EFFECT_FIELDS','DEFAULT_CAPABILITIES']:
                    lines=[next(line for line in text.splitlines() if line.startswith(key+' = ')) for text in texts]
                    values=[ast.literal_eval(line.split(' = ',1)[1]) for line in lines]
                    if isinstance(values[0],set):
                        assert values[0]<=values[1] and values[0]<=values[2]
                        combined=values[1]|values[2]
                    else:
                        combined={k:values[1][k]|values[2][k] for k in values[0]}
                        assert all(values[0][k]<=values[1][k] and values[0][k]<=values[2][k] for k in values[0])
                    merged_line=key+' = '+repr(combined)
                    texts=[text.replace(line,merged_line) for text,line in zip(texts,lines)]
                with tempfile.TemporaryDirectory() as td:
                    paths=[Path(td)/str(i) for i in range(3)]
                    for path,text in zip(paths,texts):path.write_text(text,encoding='utf8',newline='')
                    merged=subprocess.run(['git','merge-file','-p',str(paths[1]),str(paths[0]),str(paths[2])],capture_output=True)
            else:
                merged=subprocess.run(['git','merge-file','-p',str(LEFT/rel),str(base),str(right)],capture_output=True)
            assert merged.returncode==0,(str(rel),merged.stderr.decode(errors='replace'))
            dest.write_bytes(merged.stdout)
        changes.append({'path':str(rel),'source_sha':sha(right),'merged_sha':sha(dest)})
    assert guards=={path:sha(Path(path)) for path in guards}
    report={'base':identity(BASE),'parent_core':identity(LEFT),'cold_core':identity(RIGHT),'core':identity(OUT),
            'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),'changes':changes,'source_guards':guards,
            'scope':'Isolated three-way candidate, not primary/full-suite/whole-stage approval'}
    target=ROOT/'validation/campaign/chapter06_buff_join_v2/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k in ['core','catalog_sha','scope']}))


if __name__=='__main__':main()
