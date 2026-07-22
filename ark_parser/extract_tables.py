"""Extract data tables from Arknights AB bundles to data/tables/."""
import os
import UnityPy

AB_DIR = 'E:/Hypergryph Launcher/games/Arknights Game/Arknights_Data/StreamingAssets/AB/Windows/anon'
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'tables')

# Table name prefixes to look for
TABLE_NAMES = [
    'character_table', 'skill_table', 'stage_table', 'activity_table',
    'charword_table', 'handbook_info_table', 'uniequip_table',
    'battle_equip_table', 'skin_table', 'retro_table',
    'roguelike_topic_table', 'sandbox_perm_table', 'building_data',
]


def extract():
    os.makedirs(OUT_DIR, exist_ok=True)
    found = {}

    for root, dirs, files in os.walk(AB_DIR):
        for fname in files:
            if not fname.endswith('.bin'):
                continue
            path = os.path.join(root, fname)
            try:
                env = UnityPy.load(path)
                for obj in env.objects:
                    if obj.type.name != 'TextAsset':
                        continue
                    data = obj.read()
                    name = str(data.m_Name) if hasattr(data, 'm_Name') else ''
                    for prefix in TABLE_NAMES:
                        if name.startswith(prefix):
                            script = data.m_Script
                            if isinstance(script, str):
                                script = script.encode('utf-8', errors='surrogateescape')
                            if len(script) > 1000:
                                out_name = f'{name}.bin'
                                out_path = os.path.join(OUT_DIR, out_name)
                                with open(out_path, 'wb') as f:
                                    f.write(script)
                                found[name] = (len(script), out_path)
                                print(f'  {name} ({len(script)} bytes) -> {out_name}')
            except Exception:
                pass

    print(f'\nExtracted {len(found)} tables to {OUT_DIR}')
    return found


if __name__ == '__main__':
    print('Scanning AB files for data tables...')
    extract()
