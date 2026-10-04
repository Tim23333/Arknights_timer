"""Opt-in blocking reconciliation before capture; preserve all existing phases."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_faust_complete_v3_candidate'
OUT=ROOT.parent/'unpack_work/campaign_selection_settle_v3_candidate'
PIN='c6cdbc1754634628913d2e3419fd9eb5ea13f3569fe4d70c14ca20c8147c9a6f'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,old,new):
    p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8');assert s.count(old)==1,(name,old);p.write_text(s.replace(old,new),encoding='utf8',newline='')
def main():
    assert core(BASE)==PIN
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    edit('content/schemas.py','fields(activation, {', 'fields(activation, {"settle_blocking", ')
    edit('content/schemas.py','        flags = activation.get("forbidden_source_flags", [])',
        '        if "settle_blocking" in activation and type(activation["settle_blocking"]) is not bool:\n            raise ContentError(identifier+": settle_blocking requires strict boolean")\n        flags = activation.get("forbidden_source_flags", [])')
    edit('domains/abilities.py','            targets = self.ctx.spatial.select(source, ability["selector"], ability=ability) if ability.get("selector") else [source]',
        '            if "settle_blocking" in activation:\n                if type(activation["settle_blocking"]) is not bool:raise ValueError("settle_blocking requires strict boolean")\n                if activation["settle_blocking"]:\n                    self.ctx.spatial.blocking()\n                    if not self.ctx.active(source) or self.ctx.state().get("finished"):\n                        raise ActivationRejected("Source became inactive during blocking settlement")\n            targets = self.ctx.spatial.select(source, ability["selector"], ability=ability) if ability.get("selector") else [source]')
    target=ROOT/'validation/campaign/selection_settle_v1/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    report={'parent_core':PIN,'core':core(OUT),'full_stage_executed':False}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
