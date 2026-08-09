# data/ — 游戏资源解包目录

本目录存放《明日方舟》客户端的解包产物，**体积太大不入库**（.gitignore 已排除，
仅保留本说明）。克隆仓库后需要自行解包填充，工具的部分功能依赖这些产物。

## 目录结构（解包后）

| 子目录 | 内容 | 谁在用 |
|---|---|---|
| `anon/` | 加密数据表 AB 的解包结果（`*_unpacked` 目录） | `extract_tables.py` 的输入 |
| `tables/` | 从 anon 提取的数据表 bin（`character_table*`、`enemy_handbook_table*`、`skill_table*` 等）+ `effect_frames.json` | 运行时敌人/干员名称与属性数据库 |
| `battle/` | 战斗 prefab（`enm_pfb_*`、弹道 `[uc]projectiles`） | 生效帧提取 |
| `chararts/`、`charpack/` | 我方干员 spine 动画 / 参数 | 生效帧提取 |
| `refs/arts/` | 敌人 spine 动画（`enm_art_*`） | 生效帧提取 |
| `arts/`、`audio/`、`avg/`、`ui/` 等 | 其余全量资源 | 浏览/分析用，运行时不依赖 |

## 解包步骤

1. **找到游戏 AB 文件**（PC 官服示例，其他服/模拟器路径类推）：
   ```
   <游戏目录>/Arknights_Data/StreamingAssets/AB/Windows/anon/
   ```
2. **用本仓库内置的 AssetStudio-ArknightsStudio 解包**
   （`AssetStudio-ArknightsStudio/`，已对 Arknights 自定义 LZHAM/CAB 格式打补丁）：
   - GUI：加载上述 AB 目录后 Export，输出到 `data/` 下对应子目录；
     anon 数据表输出到 `data/anon/`。
   - 补丁说明：本仓库的 `AssetStudio/BundleFile.cs` 会把内层 CAB 一律落盘为
     `<文件名>_unpacked/`，后续脚本直接读取这些目录。
3. **提取数据表**（仓库根目录，需 Python 环境）：
   ```bash
   python extract_tables.py
   ```
   自动扫描 `data/anon/` 中的 CAB，按表名前缀识别，输出 13 个数据表到 `data/tables/`。
   AB 文件名 hash 后缀随游戏版本变化，脚本按前缀匹配，**版本更新后重新跑即可，无需改代码**。
4. **（可选）提取动作生效帧**（需系统 Python + UnityPy）：
   ```bash
   python ark_parser/extract_effect_frames.py
   ```
   输出 `data/tables/effect_frames.json`。依赖步骤 2 中解出的 `battle/`、
   `chararts/`、`charpack/`、`refs/arts/`。不做此步则详情页「生效帧」tab 为空，
   其余功能不受影响。

## 运行时最低需求

- 敌人名称：`data/tables/enemy_handbook_table*.bin`
- 干员名称：`data/tables/character_table*.bin`（或 `ark_parser/char_names.json`）
- 缺表时工具会退化为显示游戏内 ID（如 `enemy_1045_hammer`），扫描与数值读取不受影响。

## 版本更新后

游戏大版本更新只需重做步骤 2-3（和可选的 4）：覆盖解包到新版本 AB，
重跑 `extract_tables.py`。若内存扫描偏移失效，另需刷新逆向偏移——
见 `tools/enemy_health/update_from_unpack.py`（从新版 `Ark_data/dump.cs` 重新生成）。
