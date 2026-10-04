"""Fresh memory-preflight V2 three-way composition, preserving frozen inputs."""
import ast, hashlib, json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.candidates.m79_rebirth_environment.prepare import core, merge, sha
U=ROOT.parent/'unpack_work'
PINS={
'campaign_m88_corrected_death_environment_candidate':'3577e4cd2621218cbb819f3c4b21f32922f562c9176d26ab80681bc91f587af1',
'campaign_m82_disk_environment_candidate':'65134744f50a9a1641f339965a8f4925927e5de51aedff9a39eea0550e887522',
'campaign_m86_immunity_environment_candidate':'6013ef4e0f94e188391fb2593d681914b95291862acea662f292200bb644a1f6',
'campaign_m75_periodic_packets_candidate':'348c5671adfd73adb501c67a3dd4c51ce4f88228e45dcc6b1026c6eb2822bd57',
'campaign_m78_owned_attachment_candidate':'27d8ba218d90e6880a4f8704418871a517e5a6f30f034a79db8b04ca46a0cf74'}
def guards(root):
 return {p.relative_to(root).as_posix():sha(p) for p in sorted((root/'ark_sim').rglob('*')) if p.is_file() and p.suffix in ('.py','.json')}
def schema_union(original,desired,current):
 def nodes(text):return {n.targets[0].id:n for n in ast.parse(text).body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)}
 texts=[original,desired,current];trees=[nodes(t) for t in texts]
 for key in ('FIELDS','EFFECT_FIELDS','DEFAULT_CAPABILITIES'):
  trees=[nodes(t) for t in texts]
  values=[ast.literal_eval(t[key].value) for t in trees]
  def union(a,b):
   if isinstance(a,set) and isinstance(b,set):return a|b
   if isinstance(a,dict) and isinstance(b,dict):return {k:union(a[k],b[k]) if k in a and k in b else (a[k] if k in a else b[k]) for k in sorted(a.keys()|b.keys())}
   if a!=b:raise ValueError('Non-additive schema declaration '+key)
   return a
  combined=union(values[1],values[2])
  for index in range(3):
   segment=ast.get_source_segment(texts[index],trees[index][key]);texts[index]=texts[index].replace(segment,key+' = '+repr(combined),1)
 return texts
def compose(common,base,incoming,out,label):
 if out.exists():raise ValueError('Preserve existing candidate '+str(out))
 roots=(common,base,incoming);before={str(r):guards(r) for r in roots}
 writes={};rows={}
 for p in sorted((incoming/'ark_sim').rglob('*.py')):
  rel=p.relative_to(incoming/'ark_sim');key=rel.as_posix();a=common/'ark_sim'/rel;b=base/'ark_sim'/rel
  if a.exists() and a.read_bytes()==p.read_bytes():continue
  if not a.exists():
   if b.exists() and b.read_bytes()!=p.read_bytes():raise ValueError('Differing added file '+key)
   value=p.read_text(encoding='utf8');h=[]
  else:
   texts=[a.read_text(encoding='utf8'),p.read_text(encoding='utf8'),b.read_text(encoding='utf8')]
   if key=='content/schemas.py':texts=schema_union(*texts)
   if key=='domains/lifecycle.py':
    old='        if self.ctx.terrain is None:'
    guard='        if self.ctx.terrain is None and not self.ctx.get(ref,("lifecycle","death_projectiles")):'
    texts[0]=texts[0].replace(old,guard,1)
    texts[1]=texts[1].replace('        if self.ctx.terrain is None and getattr(self.ctx, "attachments", None) is None:',guard[:-1]+' and getattr(self.ctx, "attachments", None) is None:',1)
    old='        if getattr(self.ctx, "controls", None) is None:'
    guard='        if getattr(self.ctx, "controls", None) is None and getattr(self.ctx,"rebirth",None) is None:'
    texts[0]=texts[0].replace(old,guard,1)
    texts[1]=texts[1].replace('        if getattr(self.ctx, "controls", None) is None and getattr(self.ctx, "attachments", None) is None:',guard[:-1]+' and getattr(self.ctx, "attachments", None) is None:',1)
   try:value,h=merge(*texts)
   except ValueError as e:raise ValueError(key+': '+str(e)) from e
  ast.parse(value,filename=key);writes[key]=value;rows[key]={'common':sha(a) if a.exists() else None,'base':sha(b) if b.exists() else None,'incoming':sha(p),'hunks':h}
 catalog=json.loads((base/'ark_sim/rules/contracts.json').read_bytes());ancestor=json.loads((common/'ark_sim/rules/contracts.json').read_bytes());inc=json.loads((incoming/'ark_sim/rules/contracts.json').read_bytes())
 originals={r['id']:r for r in ancestor['contracts']};byid={r['id']:r for r in catalog['contracts']};added=[]
 for r in inc['contracts']:
  if r['id'] in originals and r==originals[r['id']]:continue
  if r['id'] in byid:
   if byid[r['id']]!=r:raise ValueError('Conflicting contract '+r['id'])
  else:catalog['contracts'].append(r);added.append(r['id'])
 if added:writes['rules/contracts.json']=json.dumps(catalog,ensure_ascii=False,indent=2)+'\n'
 assert before=={str(r):guards(r) for r in roots}
 shutil.copytree(base/'ark_sim',out/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 for key,value in writes.items():
  p=out/'ark_sim'/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf8',newline='')
 fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');(out/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(base/fixture,out/fixture)
 after={str(r):guards(r) for r in roots};assert before==after
 report={'status':'constructed_not_tested','core':core(out),'parents':{str(r):core(r) for r in roots},'parent_source_before':before,'parent_source_after':after,'hunks':rows,'changed':sorted(writes),'added_contracts':added,'output_source':guards(out),'whole_stage_executed':False,'client_verified':False}
 dest=ROOT/'validation/campaign'/label;dest.mkdir(parents=True,exist_ok=True);(dest/'composition.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='')
 print(json.dumps({'candidate':str(out),'core':report['core'],'changed':report['changed']}))
 return out
def main():
 for name,pin in PINS.items():
  if core(U/name)!=pin:raise ValueError('Frozen core drift '+name)
 m90=U/'campaign_m90_disk_immunity_candidate'
 if not m90.exists():m90=compose(U/'campaign_m88_corrected_death_environment_candidate',U/'campaign_m82_disk_environment_candidate',U/'campaign_m86_immunity_environment_candidate',m90,'m90_disk_immunity')
 elif core(m90)!='33deef4c127c737709b329bf84fba88d987142a7fb17d3ef54722eb0478f48b2':raise ValueError('Existing M90 drift')
 compose(U/'campaign_m75_periodic_packets_candidate',m90,U/'campaign_m78_owned_attachment_candidate',U/'campaign_m91_complete_c4_candidate','m91_complete_c4')
if __name__=='__main__':main()
