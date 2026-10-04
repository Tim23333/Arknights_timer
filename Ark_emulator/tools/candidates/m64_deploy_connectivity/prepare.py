"""Construct opt-in placement connectivity branch from unchanged M58."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m64_deploy_connectivity_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    if core(BASE)!='1ef9635ee70a8159e0523156aeeb177329d19d12a26185b98b9d9fa55ea3c3d5':raise ValueError('Frozen base changed')
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    def edit(name,old,new):
        p=OUT/'ark_sim'/name;b=p.read_bytes();a=old.encode();c=new.encode()
        if b'\r\n' in b:a=a.replace(b'\n',b'\r\n');c=c.replace(b'\n',b'\r\n')
        if b.count(a)!=1:raise ValueError('Patch anchor changed:'+name)
        p.write_bytes(b.replace(a,c))
    shutil.copyfile(Path(__file__).with_name('connectivity.py'),OUT/'ark_sim/domains/deploy_connectivity.py')
    edit('content/schemas.py','"deployable": {"stock",','"deployable": {"connectivity", "stock",')
    edit('content/schemas.py','        stock=components.get("deployable",{}).get("stock")','''        connectivity=components.get('deployable',{}).get('connectivity')
        if connectivity is not None:
            from ..domains.deploy_connectivity import validate_profile
            try:validate_profile(connectivity)
            except ValueError as error:raise ContentError(identifier+': '+str(error)) from error
        stock=components.get("deployable",{}).get("stock")''')
    edit('content/compiler.py','        validate_tile_fields(definitions,selected_scene)','''        validate_tile_fields(definitions,selected_scene)
        from ..domains.deploy_connectivity import validate_scenario as validate_connectivity
        validate_connectivity(definitions,selected_scene)''')
    edit('content/capabilities.py','        if "deployable" in components:\n            deploy(','''        connectivity=components.get('deployable',{}).get('connectivity')
        if connectivity is not None:require('deploy.connectivity',identifier+'.deployable.connectivity',scopes,connectivity['rule'])
        if "deployable" in components:
            deploy(''')
    edit('domains/deployment.py','    stock=deployable.get("stock")','''    from .deploy_connectivity import inspect as inspect_connectivity
    inspect_connectivity(context,definition,position,deployable)
    stock=deployable.get("stock")''')
    edit('domains/deployment.py','    stock=plan.get("stock_payment")','''    from .deploy_connectivity import inspect as inspect_connectivity
    inspect_connectivity(context,context.program.definitions[plan['definition']],plan['position'],context.get(ref,('deployable',)))
    stock=plan.get("stock_payment")''')
    edit('domains/providers.py','from .qualified_areas import qualified_cell_offsets','from .qualified_areas import qualified_cell_offsets\nfrom .deploy_connectivity import ground_routes')
    edit('domains/providers.py','BUILTIN_PROVIDERS = {','BUILTIN_PROVIDERS = {\n    "model.deploy.ground_connectivity": ground_routes,')
    p=OUT/'ark_sim/rules/contracts.json';catalog=json.loads(p.read_bytes())
    catalog['contracts'].append({'id':'deploy.connectivity','kind':'policy','owner':'scenario',
        'inputs':[{'name':name,'type':kind,'required':True} for name,kind in [('grid','record'),('routes','record_list'),('occupied','record_list'),('proposed','record'),('parameters','value_map')]],
        'outputType':'decision','outputSchema':{'type':'decision'},'implementations':['expression','graph','provider'],
        'pureEvaluation':True,'writesStateDirectly':False,'versionsRequired':True,'contractVersion':1,'status':'declared',
        'description':'Opt-in placement connectivity over explicitly protected original ground routes and effective grid snapshots.'})
    p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    changes={p.relative_to(OUT/'ark_sim').as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json') and (not (BASE/'ark_sim'/p.relative_to(OUT/'ark_sim')).exists() or p.read_bytes()!=(BASE/'ark_sim'/p.relative_to(OUT/'ark_sim')).read_bytes())}
    report={'core':core(OUT),'parent':core(BASE),'changed':changes,'tested':False,'whole_stage_executed':False}
    out=ROOT/'validation/campaign/m64_connectivity/composition.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(report))


if __name__=='__main__':main()
