"""Offline source closure for actual Ray-death spawned sealed ground."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter07.native_assets_v1 import NativeAssets,bson_source,find_templates
out=ROOT/'packages/campaign/chapter09_consumers/mandra/source.token047.v1.json'
if out.exists():raise FileExistsError(out)
assets=NativeAssets();path=ROOT.parent/'unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab';prefab=assets.closure(path,'trap_047_mandrablock');keys=find_templates(prefab);closure=bson_source(keys)
table=ROOT.parent/'unpack_work/campaign_tables/character_table.json';character=json.loads(table.read_bytes()).get('trap_047_mandrablock')
row={'schema':'ark-sim/mandra-source-token047/v1','offline_only':True,'native_prefab':prefab,'native_character':character,'character_table_key_missing':character is None,'source_character_table':{'path':str(table),'sha256':hashlib.sha256(table.read_bytes()).hexdigest()},'BSON':closure,'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};out.write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'path':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'classes':sorted({x['native_class'] for x in prefab['components'].values()}),'templates':sorted(keys),'character_table_key_missing':character is None}))
