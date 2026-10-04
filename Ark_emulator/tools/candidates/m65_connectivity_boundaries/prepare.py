"""Fix actual M64 merge/null/creation boundaries without rewriting its proof."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m64_deploy_connectivity_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m65_connectivity_boundaries_v2_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    if core(BASE)!='de0d2062e53b016083a3f2a6935a4c112205436708331070f1985febd000fea0':raise ValueError('Frozen M64 core changed')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    def edit(name,old,new):
        p=OUT/'ark_sim'/name;b=p.read_bytes();a=old.encode();c=new.encode()
        if b'\r\n' in b:a=a.replace(b'\n',b'\r\n');c=c.replace(b'\n',b'\r\n')
        if b.count(a)!=1:raise ValueError('Patch anchor changed:'+name)
        p.write_bytes(b.replace(a,c))
    edit('content/schemas.py',"        if connectivity is not None:\n            from ..domains.deploy_connectivity", "        if 'connectivity' in components.get('deployable',{}):\n            from ..domains.deploy_connectivity")
    edit('domains/deploy_connectivity.py',"        profile=definition.get('components',{}).get('deployable',{}).get('connectivity')\n        if profile is not None:profiles.append(profile)","        profile=definition.get('components',{}).get('deployable',{}).get('connectivity')\n        if 'connectivity' in definition.get('components',{}).get('deployable',{}):profiles.append(profile)")
    edit('domains/deploy_connectivity.py',"            profile=value.get('components',{}).get('deployable',{}).get('connectivity')\n            if profile is not None:profiles.append(profile)",'''            components=value.get('components',{})
            if value.get('definition') in definitions:
                from ..content.overlays import merge
                components=merge(thaw(definitions[value['definition']].get('components',{})),thaw(components))
            if 'connectivity' in components.get('deployable',{}):profiles.append(components['deployable']['connectivity'])''')
    edit('domains/deploy_connectivity.py','def inspect(context,definition,position,deployable):\n    profile=deployable.get(\'connectivity\')\n    if profile is None:return',"def inspect(context,definition,position,deployable,*,entity=None,phase='prepare'):\n    if 'connectivity' not in deployable:return\n    profile=deployable['connectivity']")
    edit('domains/deploy_connectivity.py',"    prototype={'definition_id':definition['id'],'components':thaw(definition.get('components',{})),'tags':list(definition.get('tags',()))}",'''    if not isinstance(position,Mapping) or set(position)!={'row','col'} or any(type(v) not in (int,float) for v in position.values()):raise ValueError('connectivity placement position invalid')
    r,c=project_cell(position);proposed={'row':r,'col':c}
    prototype=thaw(entity) if entity is not None else {'definition_id':definition['id'],'components':thaw(definition.get('components',{})),'tags':list(definition.get('tags',()))}
    prototype['components']['deployable']=thaw(deployable)''')
    edit('domains/deploy_connectivity.py',"'routes':thaw(routes),'occupied':occupied,'proposed':dict(position),'parameters':thaw(profile['parameters'])", "'routes':thaw(routes),'occupied':occupied,'proposed':proposed,'parameters':thaw(profile['parameters'])")
    edit('domains/deploy_connectivity.py',"extra={'source':prototype})","extra={'source':prototype,'placement_phase':phase})")
    edit('domains/deployment.py',"inspect_connectivity(context,context.program.definitions[plan['definition']],plan['position'],context.get(ref,('deployable',)))", "inspect_connectivity(context,context.program.definitions[plan['definition']],context.get(ref,('spatial','position')),context.get(ref,('deployable',)),entity=context.entity(ref),phase='record')")
    edit('domains/lifecycle.py',"        if self.ctx.terrain is None and self.ctx.tile_contacts is None and kwargs.get('active', True)",'''        definition_id=args[0] if args else kwargs.get('definition_id')
        definition=self.ctx.program.definitions.get(definition_id,{})
        has_connectivity=('connectivity' in definition.get('components',{}).get('deployable',{}) or
            'connectivity' in (kwargs.get('component_overrides') or {}).get('deployable',{}))
        if not has_connectivity and self.ctx.terrain is None and self.ctx.tile_contacts is None and kwargs.get('active', True)''')
    edit('domains/lifecycle.py',"        with self.ctx.session.atomic():\n            return self._create(*args, **kwargs)",'''        with self.ctx.session.atomic():
            ref=self._create(*args, **kwargs)
            if has_connectivity and self.ctx.active(ref):
                from .deploy_connectivity import inspect
                inspect(self.ctx,self.ctx.definition(ref),self.ctx.get(ref,('spatial','position')),self.ctx.get(ref,('deployable',)),entity=self.ctx.entity(ref),phase='created')
            return ref''')
    edit('domains/lifecycle.py','        merge(components, thaw(component_overrides or {}))','''        merge(components, thaw(component_overrides or {}))
        connectivity=components.get('deployable',{})
        if 'connectivity' in connectivity:
            from .deploy_connectivity import validate_profile
            validate_profile(connectivity['connectivity'])''')
    edit('domains/lifecycle.py','        spatial["facing"] = facing','''        spatial["facing"] = facing
        if active and 'connectivity' in components.get('deployable',{}):
            from .deploy_connectivity import inspect
            inspect(self.ctx,definition,spatial['position'],components['deployable'],phase='create')''')
    report={'schema':'ark-sim/connectivity-boundary-revision/v1','core':core(OUT),'parent':core(BASE),
        'changes':{p.relative_to(OUT/'ark_sim').as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*.py') if p.read_bytes()!=(BASE/'ark_sim'/p.relative_to(OUT/'ark_sim')).read_bytes()},
        'source_catalog_sha256':sha(OUT/'ark_sim/rules/contracts.json'),'tested':False,'actual_client_verified':False}
    p=ROOT/'validation/campaign/m65_connectivity/composition.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))


if __name__=='__main__':main()
