"""Create opt-in periodic field producer without altering frozen M68."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m62_periodic_fields_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    if core(BASE)!='1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8':raise ValueError('Frozen parent changed')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    def edit(name,old,new):
        p=OUT/'ark_sim'/name;b=p.read_bytes();a=old.encode();c=new.encode()
        if b'\r\n' in b:a=a.replace(b'\n',b'\r\n');c=c.replace(b'\n',b'\r\n')
        if b.count(a)!=1:raise ValueError('Field integration anchor changed:'+name)
        p.write_bytes(b.replace(a,c))
    shutil.copyfile(Path(__file__).with_name('periodic_fields.py'),OUT/'ark_sim/domains/periodic_fields.py')
    edit('domains/tile_mechanics.py',"        if isinstance(p,Mapping) and p.get('type')=='contact_lifecycle':", "        if isinstance(p,Mapping) and p.get('type')=='periodic_effect_field':\n            from .periodic_fields import validate_profile\n            validate_profile(p);continue\n        if isinstance(p,Mapping) and p.get('type')=='contact_lifecycle':")
    edit('content/compiler.py','        validate_tile_fields(definitions,selected_scene)','        validate_tile_fields(definitions,selected_scene)\n        from ..domains.periodic_fields import validate_content as validate_periodic_fields\n        validate_periodic_fields(definitions,selected_scene)')
    edit('content/spatial_validation.py',"        if field_profile.get('type')=='occupancy_buff_field':",'''        if field_profile.get('type')=='periodic_effect_field':
            from ..domains.tile_fields import board,same_data
            if not same_data(board(tile),field_profile['expected_blackboard']):fail(location,'periodic field blackboard not exactly bound')
        elif field_profile.get('type')=='occupancy_buff_field':''')
    edit('content/capabilities.py',"        if profile.get('type')=='contact_lifecycle':require(", "        if profile.get('type')=='periodic_effect_field':\n            require('time.quantize',scenario['id']+'.periodic_fields')\n            require('field.trigger',scenario['id']+'.periodic_fields',explicit=profile['trigger']['rule'])\n            require('field.members',scenario['id']+'.periodic_fields',explicit=profile['membership']['rule'])\n        elif profile.get('type')=='contact_lifecycle':require(")
    edit('domains/providers.py','BUILTIN_PROVIDERS = {','from .periodic_fields import uniform_trigger,cell_combat_members\n\nBUILTIN_PROVIDERS = {\n    "model.field.uniform_trigger": uniform_trigger,\n    "model.field.cell_combat_members": cell_combat_members,')
    edit('domains/context.py','        self.tile_contacts = None','        self.tile_contacts = None\n        self.periodic_fields = None')
    edit('adapters/api.py','        self._commands = []','''        if any(p.get('type')=='periodic_effect_field' for p in self.ctx.spatial.grid.tile_mechanics.values()):
            from ark_sim.domains.periodic_fields import PeriodicFieldSystem
            self.ctx.periodic_fields=PeriodicFieldSystem(self.ctx)
        self._commands = []''')
    edit('adapters/api.py','        initialize_tile_fields(self.ctx)','        initialize_tile_fields(self.ctx)\n        if self.ctx.periodic_fields is not None:self.ctx.periodic_fields.initialize()')
    edit('adapters/api.py','        if self.ctx.timeline is not None:\n            for name, handler in self.ctx.timeline.handlers.items():','''        if self.ctx.periodic_fields is not None:
            self.session.register_handler('domain.field.pulse',self.ctx.periodic_fields.pulse)
            self.session.add_system(self.ctx.periodic_fields.tick,phase=0)
        if self.ctx.timeline is not None:
            for name, handler in self.ctx.timeline.handlers.items():''')
    edit('domains/lifecycle.py','            self.ctx.emit("scenario.finished", result)','            if self.ctx.periodic_fields is not None:self.ctx.periodic_fields.tick(session)\n            self.ctx.emit("scenario.finished", result)')
    p=OUT/'ark_sim/rules/contracts.json';d=json.loads(p.read_bytes())
    for name,inputs,output in [('field.trigger',[('field','record'),('blackboard','value_map'),('samples','record_list'),('phase','string'),('parameters','value_map')],'record'),
                               ('field.members',[('field','record'),('candidates','entity_list'),('selection_states','record'),('combat_states','record'),('parameters','value_map')],'entity_list')]:
        d['contracts'].append({'id':name,'kind':'calculation','owner':'scenario','inputs':[{'name':key,'type':kind,'required':True} for key,kind in inputs],
            'outputType':output,'outputSchema':{'type':output},'implementations':['expression','graph','provider'],
            'pureEvaluation':True,'writesStateDirectly':False,'versionsRequired':True,'contractVersion':1,'status':'declared',
            'description':'Explicit source-free periodic field sampled timing/membership; World writes occur at domain boundary.'})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    report={'core':core(OUT),'parent':core(BASE),'catalog_sha256':sha(p),'tested':False,
        'required_integration':'M72 explicit no_source_damage and source=None availability consumer before real damage fields'}
    f=ROOT/'validation/campaign/m62_periodic_fields/composition.json';f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))


if __name__=='__main__':main()
