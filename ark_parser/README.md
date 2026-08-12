# ark_parser — 游戏数据解析管线

从游戏 AB 包解出原始数据表并解析成 JSON，供主程序与模拟器使用。

## 我方数据（character/）

```bash
cd ark_parser/character
python extract_character_data.py
```

输出 `data/`：`characters.json`（1368 条）、`skills.json`（1803 个）、
`devices.json`、`battle_equip.json`、`uniequip.json`。子目录内另有
`00_overview.md` 等解析原理文档。

## 敌方数据（enemy/）

```bash
cd ark_parser/enemy
python extract_enemy_data.py
```

输出 `data/`：`enemy_database.json`、`enemy_handbook.json`、
`stage_enemy_usage.json`、`levels/*.json`、`stage_sim_bundle.json` 等。
子目录内 `00_overview.md`～`11_skill_prefab_catalog.md` 为完整逆向文档。

## 生效帧提取

```bash
python ark_parser/extract_effect_frames.py
```

输出 `data/tables/effect_frames.json`（敌我普攻/技能的 Spine OnAttack 帧与
弹道速度）。

## 顶层脚本

- `extract_tables.py` — 从 `data/anon/`（base+hot 伪解包目录）提取 26 张
  数据表到 `data/tables/`。
- `char_names.json` — 干员 ID → 中文名缓存（自动重建）。

游戏更新后的完整同步流程见根目录 `README.md`。
