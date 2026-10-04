import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m80_death_environment_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m87_retire_compatibility_candidate'
PIN='1dad89a7eabf04a0bf0633bacc14ad303a2d59196689af1e24d0858de4df36a2'


def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    assert core(BASE)==PIN and not OUT.exists()
    before='            self.retire(ref, "dead", damage_attribution=event if event.get("source_policy") == "none" else None)'
    after='''            if event.get("source_policy") == "none":
                self.retire(ref, "dead", damage_attribution=event)
            else:
                self.retire(ref, "dead")'''
    s=(BASE/'ark_sim/domains/lifecycle.py').read_text(encoding='utf8');assert s.count(before)==1
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (OUT/'ark_sim/domains/lifecycle.py').write_text(s.replace(before,after),encoding='utf8',newline='')
    fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/fixture,OUT/fixture)
    report={'parent_core':PIN,'core':core(OUT),'scope':'Ordinary retirement keeps original two-argument call; only explicit no-source passes new attribution','tests_pending':True}
    out=ROOT/'validation/campaign/m87_retire_compatibility';out.mkdir(parents=True,exist_ok=True);(out/'composition.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))


if __name__=='__main__':main()
