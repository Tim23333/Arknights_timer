"""Copy frozen v5 and add opt-in generic ray/collision projections only."""
import hashlib,json,shutil,sys,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';OUT=ROOT.parent/'unpack_work/campaign_ballista_directional_v1_candidate';PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90';REPORT=ROOT/'validation/campaign/chapter05_ballista_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
 assert core(BASE)==PIN
 if OUT.exists():raise ValueError('Preserve earlier candidate')
 before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')};writes={};providers=(BASE/'ark_sim/domains/providers.py').read_text(encoding='utf8');anchor='from . import projectile_profiles';assert providers.count(anchor)==1;providers=providers.replace(anchor,anchor+'\nfrom . import ray_projectile_profiles',1);anchor='BUILTIN_PROVIDERS = {';assert providers.count(anchor)==1;providers=providers.replace(anchor,anchor+"\n    'model.projectile.cardinal_map_ray': ray_projectile_profiles.trajectory,\n    'model.projectile.qualified_swept_ray': ray_projectile_profiles.collision,",1);writes['domains/providers.py']=providers
 text=(BASE/'ark_sim/domains/projectiles.py').read_text(encoding='utf8');anchor=' def _definition(self,instance):';assert text.count(anchor)==1
 methods=''' def _trajectory_context(self,definition):
  if definition['motion'].get('parameters',{}).get('extent_policy')!='map_bounds':return {}
  grid=self.ctx.spatial.grid
  return {'projectile_map_bounds':{'min_row':-.5,'max_row':grid.rows-.5,'min_col':-.5,'max_col':grid.cols-.5}}
 def _collision_context(self,x,definition,candidates):
  params=thaw(definition['collision'].get('parameters',{}))
  if params.get('qualified_ray') is not True:return params
  from .selection import validate_eligibility
  validate_eligibility(params.get('eligibility'),'qualified projectile eligibility')
  defaults=params['eligibility']['parameters']['defaults']
  params['projectile_selection_states']={'source':self.ctx.spatial.selection_state(x['source'],defaults),'candidates':{str(e['id']):self.ctx.spatial.selection_state(e['id'],defaults) for e in candidates}}
  params['projectile_candidate_previous_positions']=thaw(x.get('candidate_previous_positions',{}))
  return params
'''
 text=text.replace(anchor,methods+anchor,1);anchor="rule_id=motion['rule'])";assert text.count(anchor)==3;text=text.replace(anchor,"rule_id=motion['rule'],extra=self._trajectory_context(d))")
 anchor="\n   motion=d['motion'];plan=self.ctx.calc";assert text.count(anchor)==1;text=text.replace(anchor,"\n   if d['collision'].get('parameters',{}).get('qualified_ray') is True:x['candidate_previous_positions']={str(e['id']):thaw(e['components']['spatial']['position']) for e in self.ctx.session.world.entities() if e['components'].get('spatial',{}).get('position') is not None}"+anchor,1)
 anchor="   result=self.ctx.calc('projectile.collision'";assert text.count(anchor)==1;text=text.replace(anchor,"   candidates=[entity for entity in self.ctx.session.world.entities() if entity['components'].get('spatial',{}).get('position') is not None]\n   if collision.get('parameters',{}).get('qualified_ray') is True:candidates=[e for e in candidates if self.ctx.alive(e['id']) and self.ctx.selectable(e['id']) and self.ctx.effect_target_available(e['id'])]\n"+anchor,1)
 anchor="'entities':[entity for entity in self.ctx.session.world.entities() if entity['components'].get('spatial',{}).get('position') is not None]";assert text.count(anchor)==1;text=text.replace(anchor,"'entities':candidates",1);anchor="extra=thaw(collision.get('parameters',{})))";assert text.count(anchor)==1;text=text.replace(anchor,"extra=self._collision_context(x,d,candidates))",1)
 anchor="   hits=[self.ctx.session.world.resolve(ref) for ref in result['hits']]";assert text.count(anchor)==1;text=text.replace(anchor,"   if collision.get('parameters',{}).get('qualified_ray') is True:\n    x['candidate_previous_positions']={str(e['id']):thaw(e['components']['spatial']['position']) for e in self.ctx.session.world.entities() if e['components'].get('spatial',{}).get('position') is not None};self._put(x)\n"+anchor,1);writes['domains/projectiles.py']=text;writes['domains/ray_projectile_profiles.py']=Path(__file__).with_name('ray_profiles.py').read_text(encoding='utf8')
 for name,value in writes.items():ast.parse(value,filename=name)
 assert before=={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')}
 shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 for name,value in writes.items():(OUT/'ark_sim'/name).write_text(value,encoding='utf8',newline='')
 fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/fixture,OUT/fixture);assert before=={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')};REPORT.mkdir(parents=True,exist_ok=True);r={'parent_core':PIN,'core':core(OUT),'writes':list(writes),'source_parent_guard':before,'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),'scope':'Constructed, not tested; only additive providers and opt-in ray/projection paths. Do not copy entire providers over another candidate; common-v5 exact hunks required.'};p=REPORT/'composition.json';p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'writes':r['writes'],'report_sha':sha(p)}))
if __name__=='__main__':main()
