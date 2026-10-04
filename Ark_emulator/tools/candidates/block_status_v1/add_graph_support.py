"""Composable blocking policies and dependency-based projection requirements."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_block_status_v3_candidate'
OUT=ROOT.parent/'unpack_work/campaign_block_status_v5_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,old,new):
    p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8');assert s.count(old)==1,(name,old);p.write_text(s.replace(old,new),encoding='utf8',newline='')
def main():
    assert core(BASE)=='f00b098ccf3ac05144d440dd18b554af87479e8ef0178eff4f2301e061f6a5d6'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=OUT/'ark_sim/domains/block_status.py';s=p.read_text(encoding='utf8')
    s+='\n\ndef required(ctx):\n    """Declared recursive rule dependencies, including graphs wrapping this provider."""\n    bindings=ctx.program.scenario.get("rules",{})\n    selected=bindings.get("blocking.eligibility",ctx.program.ruleset.get("bindings",{}).get("blocking.eligibility"))\n    seen=set()\n    def visit(ref):\n        if ref in seen:return False\n        seen.add(ref);definition=ctx.program.definitions.get(ref,{})\n        if definition.get("implementation",{}).get("provider")=="model.blocking.status":return True\n        return any(visit(child) for child in ctx.program.dependencies.get(ref,()))\n    return visit(selected)\n'
    s=s.replace('ctx.program.dependencies.get(ref,())','ctx.program.metadata.get("dependency_edges",{}).get(ref,())')
    p.write_text(s,encoding='utf8',newline='')
    edit('domains/movement.py','        bindings=self.ctx.program.scenario.get("rules",{})\n        rule_id=bindings.get("blocking.eligibility",self.ctx.program.ruleset.get("bindings",{}).get("blocking.eligibility"))\n        definition=self.ctx.program.definitions.get(rule_id,{})\n        if definition.get("implementation",{}).get("provider")=="model.blocking.status":',
        '        from .block_status import required\n        if required(self.ctx):')
    edit('domains/buffs.py','        bindings=self.ctx.program.scenario.get("rules",{})\n        selected=bindings.get("blocking.eligibility",self.ctx.program.ruleset.get("bindings",{}).get("blocking.eligibility"))\n        uses_status=self.ctx.program.definitions.get(selected,{}).get("implementation",{}).get("provider")=="model.blocking.status"',
        '        from .block_status import required\n        uses_status=required(self.ctx)')
    p=OUT/'ark_sim/rules/contracts.json';catalog=json.loads(p.read_bytes());contract=next(c for c in catalog['contracts'] if c['id']=='blocking.eligibility')
    assert 'graph' not in contract['implementations'];contract['implementations'].append('graph')
    p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    target=ROOT/'validation/campaign/block_status_v1/graph_support_v5.json'
    report={'parent_core':core(BASE),'core':core(OUT),'catalog_sha':sha(p),'full_stage_executed':False}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
