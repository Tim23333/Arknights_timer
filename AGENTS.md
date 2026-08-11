# Arknights 干员数据解析工具

## 使用方法

### 批量提取我方全部数据（干员/技能/装置/装备/模组）

```bash
cd ark_parser/character
python extract_character_data.py
```

输出（`ark_parser/character/data/`）：
- `characters.json` — character_table 全条目（1368 条，含干员/token/trap）
- `skills.json` — 技能完整数据（1803 个，含 skchr_/sktok_）
- `devices.json` — token/trap/装置分类
- `battle_equip.json` / `uniequip.json` — 战斗装备 / 模组

### 批量提取敌方数据

```bash
cd ark_parser/enemy
python extract_enemy_data.py
```

输出（`ark_parser/enemy/data/`）：`enemy_database.json`、`enemy_handbook.json`、
`stage_enemy_usage.json` 等。游戏更新后配套运行
`python -m tools.enemy_health.update_from_unpack --assets <热更解包目录>`
重建内存偏移（generated_offsets.json）与敌人名称库（enemy_names.json）。

**数值显示规则：** 所有从 blackboard 提取的数值必须转换为标准十进制显示，不要显示原始的 IEEE 754 浮点二进制整数（如 `1065353216` → `1.0`）。转换函数：
```python
import struct
def i2f(val):
    if isinstance(val, int) and 0 <= val <= 4294967295:
        return round(struct.unpack('<f', struct.pack('<I', val))[0], 4)
    return val
```

### 提取我方/敌方动作生效帧

```bash
python ark_parser/extract_effect_frames.py    # 需 UnityPy（已含在 backend/requirements.txt，.venv 可直接跑）
```

输出：`data/tables/effect_frames.json` — 每个敌人/干员的普攻与技能：
动画名、Spine 动画事件生效帧（`OnAttack` 等，秒+帧）、弹道速度（或固定飞行时间）。
数据源：`data/refs/arts/enm_art_*`（敌人 spine）、`data/chararts`（我方 spine）、
`data/battle/enm_pfb_*`/`data/charpack`（Ability 参数 `_animKey/_preDelay/_projectileKey`）、
`data/battle/prefabs/[uc]projectiles.ab_unpacked`（弹道移动组件）。
运行时由 `tools/enemy_health/enemy_db.load_effect_frames()` 加载，在敌我详情页
「生效帧」tab 展示。

### 快速查看干员数据

```bash
# 查看干员基础信息
python -c "import json; d=json.load(open('ark_parser/character/data/characters.json',encoding='utf-8')); print(json.dumps(d.get('char_1045_svash2',{}), indent=2, ensure_ascii=False))"

# 查看技能描述（skills.json: skillId -> {levels: [{name, description, blackboard, ...}]})
python -c "import json; d=json.load(open('ark_parser/character/data/skills.json',encoding='utf-8')); [print(k, v['levels'][0].get('name',''), v['levels'][0].get('description','')[:80]) for k,v in d.items() if 'svash2' in k]"
```

### 查看干员技能详细文本

在 `skills.json` 中搜索技能 ID（格式：`skchr_<代号>_<1/2/3>`）即可查看技能描述和 blackboard 参数。

---

## 干员 ID 命名规则

格式：`char_<编号>_<代号>`

| 干员 | ID |
|---|---|
| 阿米娅 | char_002_amiya |
| 凯尔希 | char_003_kalts |
| 陈 | char_010_chen |
| 凛御银灰 | char_1045_svash2 |
| 斯卡蒂 | char_263_skadi |

代号通常为英文缩写，异格干员编号 1000+。

---

## 数据来源文件

### 自动提取流程

游戏数据分两层：**基础包**（`StreamingAssets/AB/Windows/anon/`，随大版本安装/重装更新）
和**热更包**（`Arknights_Data/PersistentData/Bundles/anon/`，每次热更新下载，覆盖同名表）。
提取时必须 base+hot 合并，hot 覆盖 base。

1. 用 ArknightsStudioCLI 以 **exportRaw** 模式解出剥离版 TextAsset（base 与 hot 各跑一遍）：
```bash
CLI="AssetStudio-ArknightsStudio/AssetStudioCLI/bin/Release/net8.0/ArknightsStudioCLI.exe"
"$CLI" "<游戏>\Arknights_Data\StreamingAssets\AB\Windows\anon"        -t textAsset -m exportRaw -g none -o <base_out>
"$CLI" "<游戏>\Arknights_Data\PersistentData\Bundles\anon"            -t textAsset -m exportRaw -g none -o <hot_out>
```
2. 把两批 `.dat` 表文件按 `data/anon/<名字>.bin_unpacked/CAB-*` 布局摆放
   （目录名排序后者优先：base 用 `base_*`，热更用 `zz_hot_*`），然后运行：
```bash
python extract_tables.py
```

脚本扫描 `data/anon/*.bin_unpacked/CAB-*`（按目录名排序，**后扫到的覆盖先扫到的**，
保证热更表生效），识别表名并提取到 `data/tables/`。

> **格式陷阱：** AssetStudio GUI「Extract folder」产出的 `CAB-*` 是 Unity
> SerializedFile（全零头），**不能**直接被 `FB` 解析器读取；只有 exportRaw
> 剥离版（`[u32 名字长度][表名][128B 签名头][FlatBuffers]`）可以。2026-08 起
> data/anon 只放剥离版伪解包目录。

当前基线（2026-08-11）：base = 2026-07-22 安装版 + hot = 2026-08-11 热更，
快照在 `unpack_work/all_tables_20260801_base/` 与 `unpack_work/hot_20260811/raw/`。

### 提取的数据表

| 表名 | 内容 |
|---|---|
| character_table | 干员基础数据 |
| skill_table | 技能完整数据 |
| stage_table | 关卡数据 |
| activity_table | 活动数据 |
| charword_table | 干员语音/台词 |
| handbook_info_table | 干员档案 |
| uniequip_table | 模组数据 |
| battle_equip_table | 战斗装备 |
| skin_table | 皮肤数据 |
| retro_table | 复刻活动数据 |
| roguelike_topic_table | 肉鸽主题数据 |
| sandbox_perm_table | 沙盒权限数据 |
| building_data | 基建数据 |
| enemy_handbook_table | 敌人图鉴 |
| enemy_database | 敌人战斗数据 |
| item_table / gacha_table / medal_table | 物品/抽卡/蚀刻章 |
| story_table / zone_table | 剧情/区域 |
| shop_client_table / climb_tower_table | 商店/爬塔 |
| arkvent_table / battle_misc_table | 活动副本/战斗杂项 |
| display_meta_table / extra_battlelog_table / hotupdate_meta_table | 展示元数据/额外战报/热更元数据 |

### 原始 AB 文件位置

基础包：`E:\Hypergryph Launcher\games\Arknights Game\Arknights_Data\StreamingAssets\AB\Windows\anon\`
热更包：`E:\Hypergryph Launcher\games\Arknights Game\Arknights_Data\PersistentData\Bundles\anon\`

> **注意：** AB 包文件名的 hash 后缀会随游戏版本更新变化，`extract_tables.py` 通过表名前缀匹配，无需手动更新文件名。

---

## 推理过程记录

### 1. 发现游戏数据存储位置

- 游戏使用 Unity 2021.3.39f1 引擎，IL2CPP 编译
- 数据表存储在 `StreamingAssets/AB/Windows/anon/` 目录的加密 AB 包中
- AB 包使用 LZHAM 压缩（Unity 已弃用的压缩格式）
- 使用 AssetStudio-Arknights 分支（支持 Arknights 自定义格式）解包 AB 文件
- 解包后得到 TextAsset 类型的二进制文件

### 2. 破解二进制格式

**文件结构：**
```
Offset 0-127:    加密/混淆头部（128字节）
Offset 128-131:  版本号（uint32）
Offset 136-139:  计数（uint32）
Offset 140-143:  条目数（uint32）= 1127（干员表）/ 1604（技能表）
Offset 144+:     索引数据
Offset ~311K+:   数据区域（Region 0 和 Region 1）
Offset ~2.3M:    字符串表（中文文本、描述）
```

**格式识别：**
- 数据是 FlatBuffers 序列化格式（不是标准 FlatBuffers，是 Arknights 自定义变体）
- 通过分析 `dump.cs` 中的 `Table` 类确认（有 `__offset`、`__string`、`__vector` 方法）
- `FlatLookupConverter` 类的 `Unpack_*` 方法处理反序列化

### 3. FlatBuffers 解析核心

**类型检测逻辑（在 `parse_value` 函数中）：**
1. 读取 4 字节有符号整数作为相对偏移
2. 计算目标位置：`target = pos + rel`
3. 尝试解析为字符串（长度前缀 + UTF-8 数据）
4. 尝试解析为 FlatBuffers 表（负 soffset → vtable）
5. 尝试解析为向量（count 前缀 + 元素偏移数组）
6. 以上都不匹配则作为原始整数

**关键发现：**
- 字典条目是 2 字段 FlatBuffers 表（key=字符串, value=数据表）
- 字段 1 指向的数据可能是 Table 或 Vector（不能假设是其中一种）
- vtable 大小为 8 时表示 2 字段表（vts=8，不是 12）

### 4. 字段映射验证

通过对比实际数据确认字段顺序：
- FlatBuffers 字段顺序与 C# 类声明顺序不同
- 通过 svash2 数据验证：`subProfessionId` 在 index 8，`name` 在 index 14，`nameEn` 在 index 23
- 使用多个干员交叉验证确保映射正确

### 5. 解析器优化

- 初始版本用 step=4 扫描整个文件（太慢）
- 优化：先快速扫描找条目位置，再单独解析
- 深度解析单独实现（`deep_parse.py`），避免批量递归导致超时
- 限制递归深度（MAX_DEPTH=6）防止无限递归

### 6. 干员数量修正

- 初始解析器只找到 75 个干员（应有 436 个）
- 原因：vtable 大小过滤条件错误（`vts != 12` 应为 `vts < 8 or vts > 200`）
- 修正后找到 436 个干员（含所有异格和变体）

### 7. 技能表提取

- 技能表文件结构与干员表相同（FlatBuffers 字典格式）
- 通过扫描 `skchr_` 和 `sktok_` 前缀识别技能条目
- 提取 1607 个技能（含角色技能和 Token 技能）
- 技能描述中包含 `<@ba.vup>`、`<$ba.cold>` 等富文本标签

---

## dump.cs 中的关键类型

| 类型 | 行号 | 用途 |
|---|---|---|
| CharacterData | 149996 | 干员主数据结构 |
| SkillData | 169672 | 技能数据 |
| SkillDataBundle | 169767 | 技能数据包（含多级） |
| TalentData | 172340 | 天赋数据 |
| AttributesData | 147071 | 属性数据（HP/ATK/DEF等） |
| BattleFormula | 319027 | 战斗伤害计算 |
| Table | 1262176 | FlatBuffers 读取器 |
| FlatLookupConverter | 201499 | 反序列化注册器 |

---

## 已知限制

1. **数值字段**：部分数值（如 `atk_scale` 的具体百分比）存储为二进制浮点数，当前解析器只能读取整数值
2. **Blackboard 参数**：技能的 blackboard 参数名已提取，但具体数值需要进一步解析二进制浮点格式
3. **嵌套深度**：`deep_parse.py` 限制递归深度为 6，极深嵌套可能截断
4. **Field 顺序**：字段映射基于 svash2 数据验证，其他干员可能存在差异（未发现异常）

---

## 文件结构

```
ark_parser/
├── character/                   # 我方数据解析（extract_character_data.py）
│   └── data/                    #   characters/skills/devices/battle_equip/uniequip.json
├── enemy/                       # 敌方数据解析（extract_enemy_data.py）
│   └── data/                    #   enemy_database/enemy_handbook/stage_enemy_usage.json 等
├── char_names.json              # 干员ID→中文名缓存（按 character_table mtime 自动重建）
└── extract_effect_frames.py     # 敌我动作生效帧提取

extract_tables.py                # 从 data/anon/（base+hot 伪解包目录）提取数据表到 data/tables/

data/anon/
├── base_20260801.bin_unpacked/      # 基础包剥离版表文件（CAB-base_*）
└── zz_hot_20260811.bin_unpacked/    # 热更包剥离版表文件（CAB-hot_*，同名覆盖 base）

data/tables/
├── character_table9fc534.bin    # 干员表二进制
├── skill_tableafb859.bin        # 技能表二进制
├── stage_table*.bin             # 关卡数据
├── activity_table*.bin          # 活动数据
└── ... (共26个数据表)
```

---

## API 接口文档

`ark_api_docs/` 目录包含明日方舟游戏服务器接口的完整文档，基于 `Ark_data/dump.cs` 逆向分析。

### 文档目录

| 文件 | 内容 |
|------|------|
| `01_architecture.md` | 网络架构总览、请求流程、错误码 |
| `02_auth.md` | 认证体系 (SDK登录/OAuth2/云认证/游戏内登录) |
| `03_account.md` | 账户核心接口 (登录/同步/版本) |
| `04_battle.md` | 战斗系统 (普通关卡/剿灭/活动/编队/回放) |
| `05_gacha.md` | 抽卡系统 (公开招募/寻访/凭证兑换) |
| `06_building.md` | 基建系统 (房间/制造站/贸易站/会客室) |
| `07_shop.md` | 商店/支付 (时装/源石/高级商店/U8支付) |
| `08_charbuild.md` | 角色养成 (升级/精英化/技能/模组/皮肤) |
| `09_social.md` | 社交系统 (好友/名片/邮件) |
| `10_roguelike.md` | 肉鸽/集成战略 |
| `11_crisis.md` | 危机合约 V1/V2 |
| `12_tower.md` | 爬塔系统 |
| `13_mail_mission.md` | 任务/签到/活动/公告 |
| `14_sync.md` | 数据同步 (全量/增量/推送/心跳) |
| `15_common_types.md` | 通用数据结构 (物品/干员/错误码) |

### 使用说明

每个接口文档包含:
- **ServiceCode**: 请求路径标识
- **请求结构**: JSON 格式的请求体示例
- **响应结构**: JSON 格式的响应体示例
- **枚举值**: 相关枚举类型的可选值
- **注意事项**: 特殊处理逻辑和边界情况

---

## 代理作战序列工具 (tools/deploy_tracker)

通过读取模拟器内存获取关卡内操作序列（部署/技能/撤退的时间、位置、朝向），
不改动游戏代码。

**已集成进主程序**（`backend/desktop_app.py`「游戏状态 / 操作记录」区块右侧）：
点「扫描操作记录」后台 locate 后 0.3s 轮询 `get_events()` 增量追加表格
（时间/操作/干员/朝向/位置，新行自动滚底）；代理作战显示静态完整序列不轮询；
「导出 JSON」与 ak_live_log 同格式（source/exportTime/stageId/battle/squad/events）。
集成要点：读取器 TCP 通道用端口 **27273**（`_get_channel`，与敌人 27271 /
RNG 27272 共存隔离）；干员中文名走 `char_names.load_char_names`，打包时已把
`ark_parser/char_names.json` + `data/tables/character_table*.bin` 内嵌（build_exe.py）。

### 内存通道（adb 方案）

复用 `tools/enemy_health/memcore.py` 的 `MemCore`（adb + memsrv/`dd` 读 Android
进程 `/proc/<pid>/mem`）。游戏指针是 Android guest 虚拟地址，宿主机 pymem 直接读
模拟器进程无法解引用（旧方案不可行的根因），必须在设备侧读取。**不需要 Windows
管理员权限**，需要 MuMu 模拟器 adb root 可用。

### 数据来源（dump.cs 逆向 + 现网实测）

- `BattleLogger.m_logs` (+0x20) — 当前战斗的实时操作记录（`List<BattleLogger.LogItem>`）
- `BattleController` 字段区 → `ReplayController.m_journal` (+0x18, inline) — 代理指挥的
  完整代理序列（metadata 含 stageId、squad 编队、logs 完整操作列表）；仅代理指挥模式存在
- `BattleLogger.LogItem` (0x30 字节): timestamp@0, uniqueId@0x8（高位含 PlayerSide 标志,
  `& 0x7FFFFFFF` 得 charInstId）, charId@0x10, op@0x18 (0=SPAWN 1=WITHDRAW 2=SKILL 3=CHEAT),
  direction@0x1C (0上1右2下3左), row@0x20, col@0x24, extraInfo@0x28
- `BattleLogger.CharInfo` (0x50 字节): charInstId@0, skinId@0x8, tmplId@0x10（现网为 NULL,
  需从 skinId 去 `#` 后缀推导）, skillId@0x18, skillIndex/skillLvl/level/phase/potentialRank 之后
- BattleController 标量用现网实测偏移 (enemy_health 2026-07 验证):
  state=0x220, speedLevel=0x228, realPlayTime=0x284；dump.cs 中旧偏移已漂移
- il2cpp 数组 `max_length` 是 int32@+0x18（+0x1C 填充是垃圾，不可按 int64 读），
  数组数据起于 +0x20；List: `_items@0x10`、`_size@0x18`

### 使用方法

```bash
# 控制台实时监控 (推荐): 实时打印每次 部署/技能/撤退, 自动增量+结束导出 JSON
python -m tools.deploy_tracker.ak_live_log [--out deploy_log.json] [--interval 0.5]

# Web 可视化: 浏览器打开 http://127.0.0.1:8793/ 实时查看时间轴, 可导出 JSON
python -m tools.deploy_tracker.web_server --port 8793

# tkinter 桌面版: 全自动定位 + 表格视图 + 导出/推送打轴工具
python tools/deploy_tracker/ak_deploy_ui.py
```

注意：自动开启的技能（SP 满自动触发）不是玩家操作，BattleLogger 不记录；
手动技能/部署/撤退均有记录。

定位全自动（无需按朝向多次部署）：关卡内至少有 1 条操作记录后，三遍堆扫描
（① 4 线程 adb 堆快照 + numpy LogItem 数值预过滤 → ② 快照内 charId 字符串校验 +
反推 items 数组 + 批量 klass 名找 List<LogItem> → ③ 批量 klass 名找持有者
BattleLogger；ReplayController 由 BattleController 字段区 klass 名扫描获得）。
进关卡部署干员后若未锁定，点页面上的「重新定位」。

---

## 桌面程序打包

### 环境要求

- Python 3.8+（项目 venv：`.venv`，Python 3.12）
- 一条命令装齐（含 PyInstaller / numpy / ziglang / UnityPy）：
  `pip install -r backend/requirements.txt`
- 清单分组：运行时（PySide6/pymem/psutil/websockets）、资源解包（UnityPy）、
  可选加速（numpy，缺失自动回退纯 Python）、打包构建（pyinstaller/ziglang，
  ziglang 仅 memsrv.c 改动后重编设备侧内存服务用，缺失不阻断打包）

### 打包命令

```bash
# 一键打包主程序 + 寻址工具（推荐）
cd backend
python build_exe.py

# 只打包主程序（跳过寻址工具）
python build_exe.py --skip-timer

# 使用 onedir 模式（调试用）
python build_exe.py --onedir

# 自定义程序名
python build_exe.py --name MyArknightsTool

# 正式版显示控制台窗口（手动调试用；测试版始终使用独立日志窗口）
python build_exe.py --console

# 跳过测试版（默认每次都会连打 正式版 + 测试版 两个 exe）
python build_exe.py --skip-test

# 跳过前端构建（沿用 backend/app/static 现有产物）
python build_exe.py --skip-frontend
```

测试版说明：默认与正式版一同产出（`ArknightsTimeline_v<版本>_Test.exe`），
保持无控制台的 windowed 模式并内嵌 `TEST_BUILD` 标记文件；`desktop_app`
检测到后（或开发时设环境变量 `AK_TEST_BUILD=1`）自动打开独立诊断日志窗口，
将扫描各阶段、ADB/游戏包版本、端口转发、内存通道和未捕获异常实时显示并同步
落盘。“一键打包日志”会生成含会话日志、环境诊断、运行状态与偏移版本的 ZIP。

打包流程：步骤 0 若 `tools/enemy_health/memsrv.c` 有更新会用 ziglang 自动重编
`bin/memsrv`（失败不阻断，运行时回退 sh+dd 慢速模式）；步骤 0.5 构建前端
排轴工具页面（`frontend/` 下 `npm run build` → `backend/app/static`，
未装 npm 或构建失败不阻断，沿用已提交产物，`--skip-frontend` 可跳过），
随后把 static 复制为快照 `build/_static_snapshot`，正式版/测试版统一从快照
打包（避免打包中途 vite build 清空重写带 hash 的 assets 导致 PyInstaller
Analysis 与 PKG 之间文件消失而 FileNotFoundError）；步骤 1 打包
AKTimerTool.exe；步骤 2 打包主程序并把寻址工具内嵌进去（同时自动
打包 `tools/` 目录含 `enemy_health/bin/memsrv`、敌人名称数据库
`enemy_handbook_table*.bin`，以及前端页面快照）。
版本管控：后端版本唯一入口 `backend/app/version.py` 的 `VERSION`（exe 文件名、
窗口标题、PE 资源均由它生成）；前端版本唯一入口 `frontend/package.json` 的
`version` 字段（页面标题与页头版本号由 vite 构建时注入，build_exe 步骤 0.5
与打包完成时打印）。发版时两处各自递增。
启动时清理 `build/`、`dist/` 失败（通常是已打包 exe 还在运行被占用）会
直接报错退出，不再静默带病打包。
主程序标题栏右侧「排轴工具」按钮点击后懒启动 127.0.0.1 随机端口的静态
HTTP 服务（`ThreadingHTTPServer` 服务 `backend/app/static`，frozen 下读
`_MEIPASS/backend/app/static`）并用系统浏览器打开页面。

### 输出文件

打包完成后，`backend/dist/` 目录下会生成：

| 文件 | 说明 |
|------|------|
| `ArknightsTimeline_v<版本>.exe` | 主程序（游戏数据显示工具，已内嵌寻址工具） |

### 分发说明

1. 只需分发 `ArknightsTimeline_v<版本>.exe` 单个文件（寻址工具已内嵌，点击"打开寻址工具"自动提取运行）
2. 寻址工具需要管理员权限才能读取游戏内存
3. 敌人监控需要 MuMu 模拟器已启动且 adb root 可用（MuMu 默认支持）；首次扫描后地址缓存保存在 exe 同目录的 `enemy_cache.pkl`
4. 首次运行可能被 Windows 安全提示拦截，选择"仍要运行"即可

### 测试打包结果

```bash
cd backend
python test_packaged_exe.py
```

该脚本会检查 exe 文件是否存在、大小是否正常，并尝试启动测试。

```


---

## 实时 RNG 追踪器 (tools/ak_live_rng)

读取模拟器内存，经静态指针链精确定位战斗随机数引擎，实时还原每次随机数调用结果
并预测后续序列（控制台实时显示）。

```bash
cd tools/ak_live_rng
python ak_rng_ui.py                      # tkinter 图形界面 (序列条图/当前值/游标位置)
python ak_live_rng.py                    # 控制台版: adb 后端 (默认, 免管理员)
python ak_live_rng.py --backend pymem    # pymem 后端 (读模拟器进程, 需管理员)
python ak_live_rng.py --engine trivial   # 改看表现随机 (默认 imp=关键随机)
python ak_live_rng.py --no-cache         # 忽略地址缓存, 强制全量扫描
python ak_live_rng.py --heuristic        # 静态链外追加启发式兜底 (调试, 会捞到无关 Random)
python test_ak_live_rng.py               # 离线自测 (70 项, 无需模拟器)
```

**功能/展示分离**：`rng_service.RngService` 是可复用的服务层（连接/定位/轮询/
地址缓存/快照），两个 UI（控制台 `ak_live_rng.py`、tkinter `ak_rng_ui.py`）
都只是消费 `svc.snapshot()` 的薄壳；其他程序复用时 `from rng_service import
RngService` 即可，注入自己的 reader（实现 read/regions）还能离线嵌入。

**已集成进主程序**（`backend/desktop_app.py`「随机数追踪」区块）：点「扫描随机数」
后台 attach+locate 后 `svc.start()` 同时轮询 `imp` 与 `trivial`；UI 定时器 150ms 读取
`snapshot(18, 预测数)["by_role"]`，分别渲染战斗随机与表现随机的预测/消耗表
（两条序列的预测数统一可调 1-500）。集成要点：

- **端口隔离**：RNG 的 adb 通道用 `TcpChannel(mc, port=27272)`（`adb_reader.RNG_TCP_PORT`），
  与敌人监控默认 27271 互不干扰；`TcpChannel(port=...)` 为可参数化端口，
  半死恢复时只杀本端口 nc（`_kill_own_nc`），`_push_memsrv` 二进制变更仍会
  全杀重建（双通道各自自愈）。
- **缓存路径冻结兼容**：`rng_service.CACHE_FILE` 在 frozen 下指向 exe 同目录
  （否则指向 _MEIPASS 临时目录每次启动丢失）。
- **导入方式**：ak_live_rng 是扁平模块（无包），desktop_app 将
  `tools/ak_live_rng` 加入 sys.path 后 `from rng_service import RngService`；
  打包时 tools/ 整体作数据文件内嵌，无需额外 hidden-import。

逆向结论（Ark_data 解包 + 联网考证）：

- **战斗 RNG = System.Random（mono mscorlib, Knuth 减法门，56×int32 种子）**，
  判定方式为 `NextDouble() < 阈值`；种子从代理数据获取或开局随机生成，保存进代理
  序列复现（PRTS 代理学；贴吧逆向帖 tieba.baidu.com/p/7475697026 确认实现）。
- 引擎对象即 `BattleController.s_randomImp` / `s_randomTrivial`（dump.cs:317298，
  静态块 +0x30/+0x38），由 `RandomFactory.Create(seed, DEFAULT)` 创建。
  **为何两条流**：`randomImp`（关键随机）用于影响战局的判定（暴击/闪避/概率天赋
  技能触发），种子随代理数据保存，代理指挥复现必须逐发一致；`randomTrivial`
  （表现随机）只驱动特效等外观表现，不进代理。若表现消耗共用同一序列，掉帧/
  倍速下表现调用次数变化会挤歪关键序列导致代理复现错位，故拆成两条独立流。
- **游戏自身持有指向 RNG 的指针链**（主定位路径，现网已端到端验证）：
  `Il2CppClass("Torappu.Battle.BattleController")` — name@0x10 / namespaze@0x18 /
  static_fields@0xB8（布局见 il2cpp.h:99-106）→ 静态块 +0x30/+0x38 →
  **`Torappu.Battle.BattleRandomWrapper` 外壳（+0x10 下钻）** →
  `Torappu.LegacyRandom` 对象 → SeedArray@0x28、inext@0x20/inextp@0x24。
  注意：本地 dump.cs 是旧版（静态字段直接声明 Random，无包装层），现网新版
  多一层 BattleRandomWrapper，klass 名运行时判定兼容。mscorlib Random /
  CompatilizedRandom(MT19937) 分支同样保留。
- **LegacyRandom 游标间距实测为 31**（mscorlib System.Random 为 21）：
  现网两次读取 (inext,inextp)=(31,0)/(0,31) 证实。追踪/推演从观测快照克隆出发、
  双游标同步自增，与间距常量无关，同一复刻代码兼容；tracker 校验放行 21/-34/31/-24。
- **类名/命名空间 C 字符串与 Il2CppClass 都在大号匿名 rw 映射里**；
  libil2cpp.so 只读段里没有，全局 metadata magic 0xFAB11BAF 也全盘搜不到
  —— metadata 被加密加载后在堆中重建。GC 堆里虽有字符串拷贝，但 klass 只引用
  metadata 区原件，故静态链**直接全 rw 单遍扫**（不做 gc 分区裁剪，否则会扫到
  拷贝串假命中）。
- 启发式兜底（`--heuristic`）：扫描 len=56/624 数组 → 反查持有者指针 + klass 名校验
  → 静态字段对。未开战时会捞到几百个无关 System.Random，故默认关闭。
- 序列还原：轮询完整状态快照，用纯 Python 复刻引擎（rng_engines.py）从上次快照
  向前推演至与观测逐字节一致，两次轮询间的每一次消耗一个不漏；预测同理。
- **新一局自动检测**：静态链引擎记录带 `watch_addr`（静态槽地址），服务层每 2s
  反查槽当前指向（`memscan.resolve_engine_obj`，含 wrapper 下钻）——重新开战
  后槽指向新建对象而旧对象内存原样残留（轮询观测不到变化不会 lost）；另连续
  ~2s 读失败（对象已释放）也按丢失处理。两者均自动触发重定位；tkinter 界面
  另有「重新扫描」按钮（`request_rescan(0)`），序号回退自动清空历史列表。

读取后端与性能（MuMu 实测）：

- adb 后端复用 `tools/enemy_health` 的 `MemCore` + 设备侧 **memsrv v2**
  （`memsrv.c` 新增模式扫描命令：u64 地址对齐哈希快路径，4MB 滑动窗口 + 64B 重叠；
  客户端 `TcpChannel.scan()`，按二进制大小判断版本自动重推）。
  设备侧扫描吞吐 ~300-600 MB/s：1.9GB gc 分区 ~2s，3.7GB 全 rw ~12s；
  对比 adb forward TCP 直读 ~16-23 MB/s（全 rw ~4min）。
- 静态链定位全程 ~15s（rw 全扫：字符串 ~4s + klass 指针回扫 ~11s + 少量校验读；
  设备繁忙时扫描吞吐可能腰斩）。定位成功后地址写入 `ak_rng_cache.pkl`，
  下次启动经三重校验（klass 名 / SeedArray 指针 / 游标范围）命中则免扫描，
  游戏重启自动失效（已现网验证缓存命中与 tracker 实时预测）。
- 扫描命中后的批量校验（数组 klass 指针预筛 + 内容读回）必须走 `read_many`
  批量读（单次 TCP 往返）；逐命中单读是毫秒级往返，几千候选会拖到几分钟。
- memsrv 单次扫描上限 MAX_NEEDLES=256（超出直接断连）：针数过多时客户端
  按 256 分批合并结果；旧版服务无扫描命令时自动回退逐块 python 扫描。

文件：`rng_engines.py`（算法复刻）、`memscan.py`（静态链 + 启发式定位）、
`tracker.py`（轮询/恢复/预测）、`adb_reader.py`（adb 后端封装）、
`rng_service.py`（**可复用服务层**：连接/定位/轮询/缓存/快照）、
`ak_live_rng.py`（控制台薄壳）、`ak_rng_ui.py`（tkinter 界面薄壳）、
`test_ak_live_rng.py`（自测，53 项）。
