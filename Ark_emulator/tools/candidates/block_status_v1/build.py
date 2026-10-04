import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'
OUT=ROOT.parent/'unpack_work/campaign_block_status_v3_candidate'
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,old,new):
    p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8');assert s.count(old)>=1,(name,old)
    p.write_text(s.replace(old,new),encoding='utf8',newline='')
def main():
    assert core(BASE)==PIN
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(Path(__file__).with_name('block_status.py'),OUT/'ark_sim/domains/block_status.py')
    edit('domains/providers.py','BUILTIN_PROVIDERS = {','from .block_status import status_blocking\n\nBUILTIN_PROVIDERS = {"model.blocking.status": status_blocking,')
    edit('domains/movement.py','from .spatial import GridTopology, route_motion_mode, project_cell, UnreachablePathError',
        'from .spatial import GridTopology, route_motion_mode, project_cell, UnreachablePathError\nfrom .selection import DEFAULT_STATE')
    edit('domains/movement.py','"paths": {"remaining": list(spatial.get("movement_path", ()))}, "states": {}',
        '"paths": {"remaining": list(spatial.get("movement_path", ()))}, "states": self.block_status(ref)')
    edit('domains/movement.py','    def blocked_by(self, ref):',
        '    def block_status(self,ref):\n        bindings=self.ctx.program.scenario.get("rules",{})\n        rule_id=bindings.get("blocking.eligibility",self.ctx.program.ruleset.get("bindings",{}).get("blocking.eligibility"))\n        definition=self.ctx.program.definitions.get(rule_id,{})\n        if definition.get("implementation",{}).get("provider")=="model.blocking.status":\n            return {"target_selection":self.selection_state(ref,DEFAULT_STATE)}\n        return {}\n\n    def blocked_by(self, ref):')
    edit('domains/buffs.py','        if any("block" in definition.get("control", {}) or any(',
        '        bindings=self.ctx.program.scenario.get("rules",{})\n        selected=bindings.get("blocking.eligibility",self.ctx.program.ruleset.get("bindings",{}).get("blocking.eligibility"))\n        uses_status=self.ctx.program.definitions.get(selected,{}).get("implementation",{}).get("provider")=="model.blocking.status"\n        if any((uses_status and definition.get("selection_flags")) or "block" in definition.get("control", {}) or any(')
    target=ROOT/'validation/campaign/block_status_v1/composition_v3.json';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf8') as f:json.dump({'parent_core':PIN,'core':core(OUT),'full_stage_executed':False},f,indent=2)
    print(json.dumps({'core':core(OUT)}))
if __name__=='__main__':main()
