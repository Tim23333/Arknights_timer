import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_branch_program_v4_candidate'
OUT=ROOT.parent/'unpack_work/campaign_branch_program_v5_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,old,new):
    p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8');assert s.count(old)==1,(name,old);p.write_text(s.replace(old,new),encoding='utf8',newline='')
def main():
    assert core(BASE)=='0a8c17a4c90d6fce156221a91f50e59fb14af57388eab015213300642b15333a'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    edit('domains/branches.py','    def available(self,key):',
        '    def facts(self):\n        return {key:{**row,"available":self.available(key)} for key,row in self.state().items()}\n    def available(self,key):')
    edit('domains/ability_arbitration.py',"            'runtime':runtime,'controls':ctx.buffs.controls(source),'time':now},row['parameters'],",
        "            'branches':ctx.branches.facts() if getattr(ctx,'branches',None) is not None else {},'runtime':runtime,'controls':ctx.buffs.controls(source),'time':now},row['parameters'],")
    edit('domains/abilities.py','             "resources": self.ctx.get(source, ("resources",), {})}, self._params(ability),',
        '             "resources": self.ctx.get(source, ("resources",), {}), "branches": self.ctx.branches.facts() if getattr(self.ctx,"branches",None) is not None else {}}, self._params(ability),')
    edit('domains/behavior_decision.py'," return {'tile_candidates':tile_candidates,", " return {'branches':ctx.branches.facts() if getattr(ctx,'branches',None) is not None else {},'tile_candidates':tile_candidates,")
    path=OUT/'ark_sim/rules/contracts.json';catalog=json.loads(path.read_bytes());contract=next(c for c in catalog['contracts'] if c['id']=='behavior.decision')
    contract['inputs'].append({'name':'branches','type':'record','required':False});path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    target=ROOT/'validation/campaign/branch_program_v1/facts_v5.json'
    with target.open('x',encoding='utf8') as f:json.dump({'parent_core':core(BASE),'core':core(OUT),'catalog_sha':sha(path),'full_stage_executed':False},f,indent=2)
    print(json.dumps({'core':core(OUT),'catalog_sha':sha(path)}))
if __name__=='__main__':main()
