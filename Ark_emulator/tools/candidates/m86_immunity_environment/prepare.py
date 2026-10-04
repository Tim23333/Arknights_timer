"""Compose frozen M88 and M84 relative to immutable M68; memory preflight first."""
import sys,json,shutil,hashlib,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.candidates.m79_rebirth_environment.prepare import merge,core,sha
COMMON=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate';BASE=ROOT.parent/'unpack_work/campaign_m88_corrected_death_environment_candidate';INCOMING=ROOT.parent/'unpack_work/campaign_m84_boundary_settle_v2_candidate';OUT=ROOT.parent/'unpack_work/campaign_m86_immunity_environment_candidate'
PINS={COMMON:'1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8',BASE:'3577e4cd2621218cbb819f3c4b21f32922f562c9176d26ab80681bc91f587af1',INCOMING:'e8fe0c931358f6f09e6e209ff70948dd1d17fb80aeae969afd71d2c8ab1bef3e'}
def guards():return {str(r):{str(p.relative_to(r)):sha(p) for p in (r/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']} for r in PINS}
def main():
 if OUT.exists():raise ValueError('New candidate only; preserve frozen roots')
 for r,pin in PINS.items():
  if core(r)!=pin:raise ValueError('Frozen parent changed '+str(r))
 before=guards();writes={};rows={}
 for p in (INCOMING/'ark_sim').rglob('*.py'):
  rel=p.relative_to(INCOMING/'ark_sim');a=COMMON/'ark_sim'/rel;b=BASE/'ark_sim'/rel;key=rel.as_posix()
  if a.exists() and p.read_bytes()==a.read_bytes():continue
  if not a.exists():
   if b.exists() and b.read_bytes()!=p.read_bytes():raise ValueError('Both parents added differing file '+key)
   result=p.read_text(encoding='utf8');hunks=[];classification='new file'
  else:
   result,hunks=merge(a.read_text(encoding='utf8'),p.read_text(encoding='utf8'),b.read_text(encoding='utf8'));classification='three-way exact-context merge' if b.read_bytes()!=a.read_bytes() else 'incoming-only'
  ast.parse(result,filename=key);writes[key]=result;rows[key]={'classification':classification,'common_sha256':sha(a) if a.exists() else None,'base_sha256':sha(b) if b.exists() else None,'incoming_sha256':sha(p),'hunks':hunks}
 # Semantic overlap: M84's outer applicability transaction wraps, rather than
 # replaces, M88's existing rebirth/death-projectile transaction and leaf _adjust.
 resource=writes['domains/resources.py'];assert all(x in resource for x in ['def _adjust_applicability(', 'def _adjust(', 'rebirth._requests', '"death_projectiles"'])
 rows['domains/resources.py']['semantic_resolution']='Nested opt-in applicability transaction preserves complete M88 canonical/rebirth/death-emission wrapper and _adjust leaf.'
 effects=writes['domains/effects.py'];assert 'if source is not None else {}' in effects and 'if ref is None: return []' in effects and 'not self.ctx.buffs.applicability.active(instance):continue' in effects
 rows['domains/effects.py']['semantic_resolution']='M72 sourceNone-safe _damage_hooks delegate preserved; actual shared Buff iterator now filters applicability.active. No nonexistent no_source_damage._hooks rewritten.'
 api=writes['adapters/api.py'];assert 'add_boundary_system' in api and 'self.ctx.rebirth.tick' in api and 'self.ctx.periodic_fields.tick' in api
 catalog=json.loads((BASE/'ark_sim/rules/contracts.json').read_bytes());incoming=json.loads((INCOMING/'ark_sim/rules/contracts.json').read_bytes());ancestor=json.loads((COMMON/'ark_sim/rules/contracts.json').read_bytes());ancestor_ids={r['id'] for r in ancestor['contracts']};byid={r['id']:r for r in catalog['contracts']};added=[]
 for row in incoming['contracts']:
  if row['id'] in byid:
   if row['id'] not in ancestor_ids and row!=byid[row['id']]:raise ValueError('Conflicting contract '+row['id'])
  elif row['id'] not in ancestor_ids:catalog['contracts'].append(row);added.append(row['id'])
 assert added==['buff.applicability'] and len({r['id'] for r in catalog['contracts']})==len(catalog['contracts'])
 writes['rules/contracts.json']=json.dumps(catalog,ensure_ascii=False,indent=2)+'\n';rows['rules/contracts.json']={'classification':'exact contract union','added':added,'count':len(catalog['contracts'])}
 # Explicit invariants for all untouched base mechanisms.
 protected=['domains/lifecycle.py','domains/rebirth.py','domains/no_source_damage.py','domains/death_projectiles.py','domains/deployment.py','domains/periodic_fields.py']
 assert not any(p in writes for p in protected)
 assert before==guards()
 # All resolution and validation above was in memory. Only now materialize.
 shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 for name,text in writes.items():p=OUT/'ark_sim'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8',newline='')
 fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/fixture,OUT/fixture)
 assert all((OUT/'ark_sim'/p).read_bytes()==(BASE/'ark_sim'/p).read_bytes() for p in protected) and before==guards()
 report={'schema':'ark-sim/three-way-composition/v1','status':'constructed_not_tested','core':core(OUT),'parents':{str(r):p for r,p in PINS.items()},'parent_source_before':before,'parent_source_after':guards(),'resolutions':rows,'changed':sorted(writes),'preserved_exact_base_files':{p:sha(BASE/'ark_sim'/p) for p in protected},'catalog_count':len(catalog['contracts']),'whole_stage_executed':False,'client_verified':False}
 path=ROOT/'validation/campaign/m86_immunity_environment/composition.json';path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'core':report['core'],'catalog_count':report['catalog_count'],'changed':report['changed']}))
if __name__=='__main__':main()
