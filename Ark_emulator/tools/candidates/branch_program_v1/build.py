import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'
OUT=ROOT.parent/'unpack_work/campaign_branch_program_v4_candidate'
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,old,new):
    p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8');assert s.count(old)==1,(name,old);p.write_text(s.replace(old,new),encoding='utf8',newline='')
def main():
    assert core(BASE)==PIN
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(Path(__file__).with_name('branches.py'),OUT/'ark_sim/domains/branches.py')
    edit('content/schemas.py',"'scenario': {","'scenario': {'branches',")
    edit('content/schemas.py',"'effects': {","'effects': {'advance_branch',")
    edit('content/schemas.py','    if effect.get("op") == "spawn_on_tiles":',
        '    if effect.get("op") == "advance_branch":\n        if set(effect)!={"op","parameters"} or not isinstance(effect["parameters"],Mapping) or set(effect["parameters"])!={"branch"} or not isinstance(effect["parameters"]["branch"],str) or not effect["parameters"]["branch"]:\n            raise ContentError(path+": advance_branch requires one explicit named program")\n    if effect.get("op") == "spawn_on_tiles":')
    edit('content/schemas.py','    elif kind == "scenario":',
        '    elif kind == "scenario":\n        if definition.get("branches") is not None:\n            from ..domains.branches import validate as validate_branches\n            validate_branches(definition["branches"],lambda e:validate_effect(e,identifier+".branches",capabilities))')
    edit('adapters/api.py','        self._commands = []',
        '        self.ctx.branches=None\n        if program.scenario.get("branches"):\n            from ark_sim.domains.branches import BranchSystem\n            self.ctx.branches=BranchSystem(self.ctx)\n        self._commands = []')
    edit('adapters/api.py','        for item in program.scenario.get("initialEntities", ()):',
        '        if self.ctx.branches is not None:self.ctx.branches.start()\n        for item in program.scenario.get("initialEntities", ()):')
    edit('adapters/api.py','        if self.ctx.timeline is not None:\n            for name, handler in self.ctx.timeline.handlers.items():',
        '        if self.ctx.branches is not None:\n            for name,handler in self.ctx.branches.handlers.items():self.session.register_handler(name,handler)\n        if self.ctx.timeline is not None:\n            for name, handler in self.ctx.timeline.handlers.items():')
    edit('domains/effects.py','        if effect["op"] == "spawn_on_tiles":',
        '        if effect["op"] == "advance_branch":\n            if getattr(self.ctx,"branches",None) is None:raise ValueError("branch program feature not loaded")\n            self.ctx.branches.advance(effect["parameters"]["branch"],source,cause)\n            return\n        if effect["op"] == "spawn_on_tiles":')
    edit('domains/lifecycle.py','        if result["finished"]:',
        '        if result["finished"] and result.get("result")=="victory" and getattr(self.ctx,"branches",None) is not None:\n            if any(row["phase"]=="running" for row in self.ctx.branches.state().values()):return\n        if result["finished"]:')
    edit('domains/lifecycle.py','            if getattr(self.ctx,"rebirth",None) is not None:self.ctx.rebirth.cancel_all("battle_terminal")',
        '            if getattr(self.ctx,"branches",None) is not None:self.ctx.branches.cancel_terminal()\n            if getattr(self.ctx,"rebirth",None) is not None:self.ctx.rebirth.cancel_all("battle_terminal")')
    edit('content/capabilities.py','        if op == "begin_attachment":',
        '        if op == "advance_branch":\n            if item["parameters"]["branch"] not in scenario.get("branches",{}):raise ContentError(path+": unknown branch program")\n            require("time.quantize",path)\n        if op == "begin_attachment":')
    edit('content/capabilities.py','    for index, entry in enumerate(scenario.get("scheduledEffects", [])):',
        '    for key,branch in scenario.get("branches",{}).items():\n        require("time.quantize",scenario["id"]+".branches."+key)\n        for phase in branch["phases"]:\n            for action in phase["actions"]:\n                for item in action["effects"]:\n                    control_effect(item,scenario["id"]+".branches."+key)\n                    effect(item,scenario["id"]+".branches."+key,[])\n    for index, entry in enumerate(scenario.get("scheduledEffects", [])):')
    target=ROOT/'validation/campaign/branch_program_v1/composition_v4.json';target.parent.mkdir(parents=True,exist_ok=True)
    report={'parent_core':PIN,'core':core(OUT),'full_stage_executed':False}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
