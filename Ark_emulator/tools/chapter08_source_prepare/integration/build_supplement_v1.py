"""Supplement raw binary/script/PPtr/provenance evidence; no runtime semantics."""
import sys,json,hashlib,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.chapter07.native_assets_v1 import NativeAssets
BASE=ROOT/'packages/campaign/chapter08_source_prepare/integration'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 catalog=json.loads((ROOT/'packages/campaign/mainline_catalog.json').read_bytes());enemies=json.loads((BASE/'enemies.native.v1.json').read_bytes());assets=NativeAssets();locks={str(ROOT/'packages/campaign/mainline_catalog.json'):sha(ROOT/'packages/campaign/mainline_catalog.json')};binary={};externals=[];lookup={}
 for name,pin in enemies['source_locks'].items():
  p=ROOT.parent/name
  if p.name.startswith('CAB-'):lookup[p.name]=p
 for c in catalog['stages']:
  if c['chapter']!=8 or not c['selected']:continue
  binary[c['level_id']]=[]
  for ref in c['original_binary_level_sources']:
   p=(ROOT/ref['path']).resolve();assert sha(p)==ref['sha256'];locks[str(p)]=sha(p);binary[c['level_id']].append({'path':str(p),'sha':sha(p),'bytes':p.stat().st_size,'raw_base64':base64.b64encode(p.read_bytes()).decode(),'typed_layout_alignment_to_fixed56_table_verified':False})
 for group in ['prefabs','projectiles']:
  for key,record in enemies[group].items():
   for ref in record.get('external_references',[]):
    cab=ref['external'].rsplit('/',1)[-1];p=lookup.get(cab);row={'parent_group':group,'parent_key':key,'source_reference':ref}
    if p is None:row['status']='source_file_pending'
    else:
     objects,trees,file=assets.load(p);pid=ref['pointer']['m_PathID'];assert pid in objects;row.update(status='exact_external_object_present',source_path=str(p),source_sha=sha(p),object_type=objects[pid].type.name,raw_object=trees[pid]);locks[str(p)]=sha(p)
    externals.append(row)
 opera_keys=sorted({a['native']['key'] for s in json.loads((BASE/'source.plan.v1.json').read_bytes())['stages'].values() for a in s['actions'] if a['native']['actionType']=='PLAY_OPERA'});opera={'keys':opera_keys,'status':'no_matching_gameobject_in_available_local_battle_CABs','method_body_semantics':'unrecovered, source native actions/routes/managed flags retained; no empty Actor or runtime no-op invented','binary_text_occurrences':[]}
 for p in [ROOT.parent/'data/anon_textassets/special_operator_tablef3dfef.dat',ROOT.parent/'data/anon_textassets/level_main_08-17.dat']:
  raw=p.read_bytes();occ={k:[i for i in range(len(raw)) if raw.startswith(k.encode(),i)] for k in opera_keys};locks[str(p)]=sha(p);opera['binary_text_occurrences'].append({'path':str(p),'sha':sha(p),'offsets':occ,'semantic_schema_decoded':False})
 for p in Path(__file__).parent.glob('*.py'):locks[str(p)]=sha(p)
 result={'schema':'ark-sim/chapter08-source-supplement/v1','fixed_catalog_ids':{'level_main_08-16':'JT8-2','level_main_08-17':'JT8-3'},'binary_stages':binary,'external_PPtr_objects':externals,'PLAY_OPERA_source':opera,'source_before':locks,'source_after':{p:sha(Path(p)) for p in locks},'reference_versions':'fixed56aee native JSON/referenceDB,local20260831 assets, frozenofficial20250327 trap tokens are distinct pinned evidence. No client alignment asserted.','runtime_authored':False,'whole_stage_executed':False};assert result['source_before']==result['source_after'];out=BASE/'source.supplement.v1.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':sha(out),'external_objects':len(externals),'opera_pending':opera_keys}))
if __name__=='__main__':main()
