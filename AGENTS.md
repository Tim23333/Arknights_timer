# Arknights 干员数据解析工具

## 使用方法

### 提取单个干员完整数据（深度解析）

```bash
cd ark_parser
python deep_parse.py <char_id>
```

示例：
```bash
python deep_parse.py char_1045_svash2    # 凛御银灰
python deep_parse.py char_002_amiya      # 阿米娅
python deep_parse.py char_263_skadi      # 斯卡蒂
```

输出文件会自动创建在 `ark_parser/<char_id>/` 文件夹下，包含：
- `<char_id>_deep.json` — 完整嵌套数据
- `README.md` — 干员摘要（天赋/技能/潜能）

**数值显示规则：** 所有从 blackboard 提取的数值必须转换为标准十进制显示，不要显示原始的 IEEE 754 浮点二进制整数（如 `1065353216` → `1.0`）。转换函数：
```python
import struct
def i2f(val):
    if isinstance(val, int) and 0 <= val <= 4294967295:
        return round(struct.unpack('<f', struct.pack('<I', val))[0], 4)
    return val
```

### 批量提取所有干员基础数据

```bash
cd ark_parser
python parse_characters.py
```

输出：`characters.json`（436 个干员）

### 批量提取所有技能数据

```bash
cd ark_parser
python parse_skill_table.py
```

输出：`skills.json`（1607 个技能）

### 快速查看干员数据

```bash
# 查看干员基础信息
python -c "import json; d=json.load(open('characters.json')); print(json.dumps(d.get('char_1045_svash2',{}), indent=2, ensure_ascii=False))"

# 查看技能描述
python -c "import json; d=json.load(open('skills.json')); [print(k,v.get('f3',[{}])[0].get('f0',''),v.get('f3',[{}])[0].get('f2','')[:80]) for k,v in d.items() if 'svash2' in k]"
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

1. 使用 AssetStudio-Arknights 解包 AB 文件到 `data/anon/` 目录
2. 运行提取脚本：
```bash
python extract_tables.py
```

脚本会自动扫描 `data/anon/` 中的 CAB 文件，识别并提取所有数据表到 `data/tables/`。

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

### 原始 AB 文件位置

游戏目录：`E:\Hypergryph Launcher\games\Arknights Game\Arknights_Data\StreamingAssets\AB\Windows\anon\`

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
├── parse_characters.py          # 批量提取干员基础数据（436个）
├── parse_skill_table.py         # 批量提取技能数据（1607个）
├── deep_parse.py                # 单个干员深度解析（含天赋/技能/潜能）
├── characters.json              # 所有干员基础数据
├── skills.json                  # 所有技能完整数据
└── char_1045_svash2/            # 凛御银灰数据文件夹
    ├── README.md                # 干员摘要（天赋/技能/潜能）
    ├── char_1045_svash2_deep.json   # 完整嵌套数据
    ├── svash2_final.json        # 基础字段数据
    ├── svash2_skills.json       # 技能数据
    ├── svash2_strings.txt       # 所有中文文本
    └── svash2_skills_strings.txt # 技能详细文本

extract_tables.py                # 自动从 data/anon/ 提取数据表到 data/tables/

data/tables/
├── character_tabled88efb.bin    # 干员表二进制
├── skill_tableafb859.bin        # 技能表二进制
├── stage_table*.bin             # 关卡数据
├── activity_table*.bin          # 活动数据
└── ... (共13个数据表)
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

## 桌面程序打包

### 环境要求

- Python 3.8+
- PyInstaller: `pip install pyinstaller`
- 项目依赖: `pip install -r backend/requirements.txt`
- 可选依赖（加速内存扫描）: `pip install numpy`
- 可选依赖（memsrv.c 改动后重新交叉编译设备侧内存服务）: `pip install ziglang`

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

# 显示控制台窗口（调试用）
python build_exe.py --console

# 测试版（带控制台窗口实时显示日志，输出 ArknightsTimeline_Test.exe 不覆盖正式版）
python build_exe.py --test
```

测试版说明：`--test` 会强制控制台模式并内嵌 `TEST_BUILD` 标记文件，
`desktop_app` 检测到后（或开发时设环境变量 `AK_TEST_BUILD=1`）将全部
内部日志（扫描各阶段/adb 诊断/通道异常/线程未捕获异常）实时输出到
控制台窗口，用于现场排查（如换机扫描失败）。

打包流程：步骤 0 若 `tools/enemy_health/memsrv.c` 有更新会用 ziglang 自动重编
`bin/memsrv`（失败不阻断，运行时回退 sh+dd 慢速模式）；步骤 1 打包
AKTimerTool.exe；步骤 2 打包主程序并把寻址工具内嵌进去（同时自动打包
`tools/` 目录含 `enemy_health/bin/memsrv`、敌人名称数据库
`enemy_handbook_table*.bin`）。

### 输出文件

打包完成后，`backend/dist/` 目录下会生成：

| 文件 | 说明 |
|------|------|
| `ArknightsTimeline.exe` | 主程序（游戏数据显示工具，已内嵌寻址工具） |

### 分发说明

1. 只需分发 `ArknightsTimeline.exe` 单个文件（寻址工具已内嵌，点击"打开寻址工具"自动提取运行）
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
