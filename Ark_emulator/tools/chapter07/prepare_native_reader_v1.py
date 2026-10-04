"""Chapter7-only offline reader: preserve native null GameObject ScriptableObject refs."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];s=(ROOT/'tools/build_chapter01_enemy_sources.py').read_text();s=s.replace('parents[1]','parents[2]',1)
old='"gameobject_name": objects[trees[pid]["m_GameObject"]["m_PathID"]].read().m_Name,'
new='"gameobject_name": objects[trees[pid]["m_GameObject"]["m_PathID"]].read().m_Name if trees[pid]["m_GameObject"]["m_PathID"] else None, "native_null_gameobject_preserved": not bool(trees[pid]["m_GameObject"]["m_PathID"]),'
assert s.count(old)==1;s=s.replace(old,new);out=ROOT/'tools/chapter07/native_assets_v1.py';assert not out.exists();out.write_text(s,encoding='utf8',newline='')
p=ROOT/'tools/chapter07/build_predefined_sources_v2.py';r=p.read_text();r=r.replace('from tools.build_chapter01_enemy_sources import NativeAssets, find_templates, bson_source, story_source','from tools.chapter07.native_assets_v1 import NativeAssets, find_templates, bson_source, story_source').replace('source.v2.reference.json','source.v3.reference.json');out=ROOT/'tools/chapter07/build_predefined_sources_v3.py';assert not out.exists();out.write_text(r,encoding='utf8',newline='');print('New local reader preserves raw null object pointer; no old reader changed')
