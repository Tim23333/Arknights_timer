"""Build M76 from immutable M68; new core never replaces old evidence."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m76_death_projectiles_v7_candidate'
PIN='1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'


def core(root):
    rows={str(p.relative_to(root/'ark_sim')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'ark_sim').rglob('*.py'))}
    return hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def edit(name,before,after):
    path=OUT/'ark_sim'/name;s=path.read_text(encoding='utf8')
    if s.count(before)!=1:raise ValueError('Ambiguous source anchor '+name)
    path.write_text(s.replace(before,after),encoding='utf8',newline='')


def main():
    assert core(BASE)==PIN and not OUT.exists()
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/fixture,OUT/fixture)
    shutil.copyfile(Path(__file__).with_name('death_projectiles.py'),OUT/'ark_sim/domains/death_projectiles.py')
    edit('content/schemas.py','"leak_loss", "revive"}', '"leak_loss", "revive", "death_projectiles"}')
    edit('content/schemas.py','        if "selection_state" in components:', '''        emissions=components.get('lifecycle',{}).get('death_projectiles')
        if emissions is not None:
            from ark_sim.domains.death_projectiles import validate
            if not isinstance(emissions,(list,tuple)):raise ContentError(identifier+': death_projectiles must be array')
            for index,spec in enumerate(emissions):
                try:validate(spec)
                except (ValueError,TypeError) as error:raise ContentError(identifier+': '+str(error)) from error
                validate_effect(spec['effect'],identifier+'.death_projectiles['+str(index)+'].effect',capabilities)
        if "selection_state" in components:''')
    edit('content/schemas.py','"attach_at_launch", "lifecycle", "on_invalid"}', '"attach_at_launch", "lifecycle", "on_invalid", "completion_blocking"}')
    edit('content/schemas.py','    if kind == "projectile":', '''    if kind == "projectile":
        if 'completion_blocking' in definition and type(definition['completion_blocking']) is not bool:
            raise ContentError(identifier+': completion_blocking must be bool')''')
    edit('content/capabilities.py','        lifecycle = components.get("lifecycle", {})', '''        lifecycle = components.get("lifecycle", {})
        for index,spec in enumerate(lifecycle.get('death_projectiles',[])):
            path=identifier+'.lifecycle.death_projectiles['+str(index)+']'
            require('lifecycle.death_emission',path,scopes,spec['rule'])
            projectile=definitions[spec['projectile_definition']]
            if projectile.get('kind')!='projectile':raise ContentError(path+': projectile definition kind required')
            if projectile['lifecycle']['source_invalid']!='retain' or projectile['lifecycle']['target_invalid']!='retain_position':
                raise ContentError(path+': postmortem source/anchor must be retained')
            effect(spec['effect'],path+'.effect',scopes)''')
    edit('domains/lifecycle.py','        self.ctx.set(ref, ("runtime", "alive"), False)', '''        if reason=='dead' and self.ctx.get(ref,('lifecycle','death_projectiles')):
            from .death_projectiles import emit
            if self.ctx.get(ref,('runtime','death_emission_in_progress'),False):return
            self.ctx.set(ref,('runtime','death_emission_in_progress'),True)
            try:emit(self.ctx,ref)
            finally:self.ctx.set(ref,('runtime','death_emission_in_progress'),False)
            if not self.ctx.alive(ref):return
        self.ctx.set(ref, ("runtime", "alive"), False)''')
    edit('domains/lifecycle.py','        if result["finished"]:', '''        if result['finished'] and result['result']=='victory' and self.ctx.projectiles is not None:
            if self.ctx.projectiles.completion_pending():return
        if result["finished"]:''')
    edit('domains/lifecycle.py','        if self.ctx.terrain is None:\n            return self._retire(ref, reason)', '''        if self.ctx.terrain is None and not self.ctx.get(ref,('lifecycle','death_projectiles')):
            return self._retire(ref, reason)''')
    edit('domains/lifecycle.py','        merge(components, thaw(component_overrides or {}))', '''        merge(components, thaw(component_overrides or {}))
        if 'death_projectiles' in components.get('lifecycle',{}):
            from .death_projectiles import validate_effective
            validate_effective(self.ctx,components)''')
    edit('domains/resources.py','    def adjust(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):', '''    def adjust(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):
        if self.ctx.get(ref,('lifecycle','death_projectiles')):
            with self.ctx.session.atomic():
                return self._adjust_death(ref,resource,delta,value=value,source=source,ability=ability,effect=effect)
        return self._adjust_death(ref,resource,delta,value=value,source=source,ability=ability,effect=effect)

    def _adjust_death(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):''')
    edit('domains/projectiles.py',' def active_casts(self,source):', ''' def completion_pending(self):
  return any(x['state']=='active' and self._definition(x).get('completion_blocking',False) for x in self._state()['instances'].values())
 def active_casts(self,source):''')
    edit('domains/providers.py','BUILTIN_PROVIDERS = {', '''from .death_projectiles import qualified_radius
BUILTIN_PROVIDERS = {
    'model.area.qualified_radius': qualified_radius,''')
    edit('domains/effects.py','                    result = self.ctx.calc("area.members",', '''                    if member_rule['implementation'].get('provider')=='model.area.qualified_radius':
                        from .death_projectiles import radius_projection
                        options={**thaw(member_rule.get('parameters',{})),**thaw(effect.get('parameters',{}))}
                        area_extra['area_selection_states']=radius_projection(self.ctx,source,candidates,options)
                    result = self.ctx.calc("area.members",''')
    edit('content/capabilities.py','        if item.get("projectile_definition"):\n            projectile=definitions[item["projectile_definition"]]', '''        if item.get('membership_rule') and rules[item['membership_rule']]['implementation'].get('provider')=='model.area.qualified_radius':
            options={**rules[item['membership_rule']].get('parameters',{}),**item.get('parameters',{})}
            require('targeting.eligibility',path+'.eligibility',explicit=options['eligibility']['rule'])
        if item.get("projectile_definition"):
            projectile=definitions[item["projectile_definition"]]''')
    catalog=OUT/'ark_sim/rules/contracts.json';d=json.loads(catalog.read_bytes())
    d['contracts'].append({'id':'lifecycle.death_emission','kind':'calculation','owner':'source',
        'inputs':[{'name':'entity','type':'entity_snapshot','required':True},{'name':'selection_state','type':'record','required':True},
            {'name':'parameters','type':'record','required':True},{'name':'clock','type':'record','required':True}],
        'outputType':'boolean','implementations':['expression','graph','provider'],'pureEvaluation':True,'writesStateDirectly':False})
    catalog.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    out=ROOT/'validation/campaign/m76_death_projectiles';out.mkdir(parents=True,exist_ok=True)
    report={'parent_core':PIN,'actual_root':str(OUT),'core':core(OUT),'status':'author construction; tests pending','whole_stage_executed':False}
    (out/'composition_v7.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))


if __name__=='__main__':main()
