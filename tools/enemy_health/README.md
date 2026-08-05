# 明日方舟敌人内存扫描模块

通过 ADB 读取 MuMu 模拟器中游戏进程内存：开局读取关卡固定出怪顺序，
并实时获取每个敌人的名称、生命周期、血量、攻击/防御/法抗/移速/攻速等数据。

## 原理

```
MuMu 模拟器 (Android)
  └── 明日方舟进程 (IL2CPP, arm64)
       └── BattleController
            ├── LevelData.waves → Wave/Fragment/SPAWN 固定出怪序列
            ├── Scheduler.m_actionQueue → 当前片段精确出场计时
            └── UnitManager.enemies → 全部当前 Enemy（含非调度器召唤）
```

主定位路径通过设备侧模式扫描查找当前 `BattleController`，沿固定字段直接取得
`Scheduler`、实时敌人列表和 `LevelData`，通常约 20-40 秒，且场上敌人数为 0 时
同样可用。地址链缓存到 `enemy_cache.pkl`。旧的内容特征全堆扫描仍保留为版本漂移
兜底；它会将第一遍扫描落盘为临时快照，后续阶段在本地重放。

> **大块读取注意（2026-07-22 修复）**：`dd` 大块读取必须头/尾 4KB 页对齐、
> 中部整 4MB 块——若把起点/终点 4MB 对齐到区域外的未映射洞，`dd` 直接 EIO
> 导致整块 32MB 丢失（确定性，非偶发）。此前扫描时灵时不灵，根因就是关键
> 对象所在区域起点前恰好有/没有洞。扫描结束若丢块会打印警告。

轮询分两档：
- **准实时 `poll_fast()`**（后端主程序/CLI 默认）：常驻 TCP 通道（`adb forward tcp:27271`）；
  详情重型数据使用独立 `27274` 通道，不阻塞主轮询。
  通道有两种模式，自动探测：
  - **memsrv 模式（默认，实测中位 ~0.7ms/帧）**：`memsrv.c` 交叉编译出的 aarch64 静态
    小程序（`bin/memsrv`），由 `nc -L` 以 socket 为 stdin/stdout 启动，
    打开 `/proc/<pid>/mem` 一次后每次读取仅一个 pread 系统调用。协议为
    小端二进制（横幅 `AKMSRV1\n`；请求 `u64 N + N×{addr,size}`；响应
    `i64 n + data`，n<0 为 -errno）。
    **v2（横幅 `AKMSRV2\n`）** 在读取协议不变的基础上新增设备侧模式扫描命令
    （`u64 SCAN_MAGIC + {addr,size,k} + k×{len,needle}` → `k×{count, addrs}`，
    k≤256，单针命中上限 65536），供 `tools/ak_live_rng` 全盘定位使用；
    客户端按二进制大小判断版本变更并自动重推重启服务，v1/旧 sh 服务自动降级。
  - **sh 兜底模式（~45ms/请求）**：`nc -L sh`，每请求 fork 一次 dd。
    memsrv 缺失或握手失败时自动使用；若 memsrv 可部署会自动升级。
  稳态每帧仅 1 次请求（上一帧敌人聚簇 span，含血量/状态/坐标/id/属性指针），
  Scheduler List 与 UnitManager 无序数组每 4 帧检查一次；后者每次重读有效槽，
  可捕获装置/技能召唤及同数量替换。属性每 3 帧轮换刷新 1 个敌人，摊平尖峰；
  BattleController/固定战斗时钟每 2 帧读一次；新刷敌人在通道内 2 批解析
  （id 字符串 + cachedData），失败兜底慢读。通道异常会在日志中说明原因
  并回退慢速 `poll()`。
- **慢速 `poll()`**：每次约 1-2 秒，逐对象 `adb exec-out`，作为兜底路径。

### memsrv 构建（已提供预编译 `bin/memsrv`，仅修改 memsrv.c 后需要）

```bash
pip install ziglang   # zig cc 交叉编译器
python -m ziglang cc -target aarch64-linux-musl -static -O2 \
    -o tools/enemy_health/bin/memsrv tools/enemy_health/memsrv.c
```

设备侧部署（推送到 `/data/local/tmp/`、生成包装脚本、启动 nc）由
`TcpChannel` 自动完成，无需手动操作。

> **死路记录（勿重走）**：Windows 侧 pymem 直读 MuMuVMMHeadless.exe 客体内存
> 已实测不可行——客体内存中的 IL2CPP 指针值在 VMM 进程里无法直接解引用
> （107 个 enemy_ 字符串 klass 链 0/107 读出）；VA→PA→host 也不是线性映射
> （同一大区域内逐页离散）。哈希多针 VMM 扫描本身可行（9s/4.96GB），但
> 定位后的指针链无法跟随，故放弃。

## 前置条件

1. **MuMu 模拟器** 已启动，明日方舟已进入战斗关卡（无需等待敌人出场）
2. **adb root** 可用。MAA 能截图只验证普通 ADB 连接，不代表有权读取 `/proc/<pid>/mem`；若工具提示无 root，请在 MuMu 设置中开启 Root 并重启模拟器
3. ADB 设备地址选择与 MAA“连接地址”一致（MuMu 主实例通常为 `127.0.0.1:16384`）；主程序“选择 ADB”页面会自动连接常见 MuMu 端口并列出在线设备
3. **Python 3.8+**，依赖 `numpy`（扫描加速）

## 使用方法

### 后端主程序页面

```bash
cd backend
python run.py
```

- `tools/enemy_health` 不再维护独立 GUI；页面统一由 `backend/desktop_app.py` 承担
- 主程序启动后可尝试缓存地址秒级进入监控
- **一键扫描**：定位当前关卡、完整固定出怪序列与实时敌人列表（通常约 20-40 秒）
- 固定敌人按预定顺序从开局显示为“未出场”，出现后实时更新，死亡/漏怪后保留为“已离场”
- 当前 Scheduler 队列内的敌人显示精确剩余游戏秒数；分支、死亡转换或召唤显示真实等待条件，不伪造秒数
- **离场敌方不显示**默认勾选；取消后显示完整历史及离场前最后一帧数据
- 表格准实时展示 (默认 0.016 秒刷新=60Hz, 可调至 0.008): 名称/编号/ID/坐标/血条/攻击/防御/法抗/移速/攻速/状态
- **显示列**可逐项勾选全部最终属性、异常状态、状态免疫、护盾，以及神经/侵蚀/灼燃/凋亡/狂躁五类损伤条；主表按与游戏 HUD 一致的“剩余/上限（剩余比例）”显示，选择会持久化。对话框右侧的**显示顺序**列表支持拖动调列序（敌方与干员表各自独立持久化），新勾选的列排在末尾，“恢复默认/全部显示”等预设同时把顺序重置为定义顺序
- **精英/Boss 损伤上限**优先使用运行时 `m_epArray[NONE]`，不再被静态 `MAX_EP=1000` 覆盖；鼠王等单位可正确显示 2000 上限
- **伤害护盾**同时显示统一 `ShieldUIController` 护盾与旧式特殊护盾。鼠王的法术屏障由三个 `mousek_shield[a/b/c]` Buff 分段保存，工具首次识别后直接轮询 Blackboard 动态值并汇总，不会每帧重扫 Buff 链
- 主表数值默认保留 **2 位小数**；“列宽自适应”按当前可见列和视口宽度智能排版，优先完整显示生命值与损伤条，并把剩余空间分配给名称、技能和出场条件列
- **迷你模式**把同一张实时敌人表移动到半透明置顶浮层；透明度只作用于背景，文字、血条数值和表格描边保持高对比。未锁定时可拖动、缩放、调整 25%-100% 透明度，并可用左键或右键点击行查看详情。锁定后按存活敌人数自动扩高、最多同时展示 20 行，左键继续穿透到后方窗口，表格区域保留滚轮浏览和右键详情；默认全局快捷键 `Alt+K` 锁定/解锁
- 主表始终把当前场上且存活的敌人置顶；未出场敌人随后，阵亡或已离场敌人置底，各组内部仍保持关卡预定/首次发现顺序
- 每行的**详情**按钮与主表同帧更新 HP/状态/损伤条/技能；原始属性、当前 Buff 和关卡全局 Buff 由独立通道持续刷新
- Buff/关卡效果同时显示中文名称、自动归纳的效果说明、中文属性公式和 Blackboard 参数解释；内部键与原始参数仍保留用于逆向核对
- 状态栏显示每帧读取耗时 (ms/帧); 轮询线程用 timeBeginPeriod(1) 保证亚 16ms 睡眠精度

### 命令行

```bash
# 实时监控（默认 2.5 秒刷新, 读帧本身约 0.05-0.1 秒）
python -m tools.enemy_health

# 准实时刷新 (0.1 秒)
python -m tools.enemy_health --interval 0.1

# 只读取一次
python -m tools.enemy_health --once

# 强制重新扫描地址（换关卡/重启游戏后）
python -m tools.enemy_health --rebuild

# 显示敌人描述
python -m tools.enemy_health --desc

# 指定 adb 路径、设备地址 / 刷新间隔
python -m tools.enemy_health --adb "D:\...\adb.exe" --serial 127.0.0.1:16384 --interval 1
```

## 输出示例

```
状态: 战斗中   倍速: 1x (x1)   战斗时间: 00:21   敌人数: 5

#  名称            编号   血量                                  攻击   防御   法抗   移速    攻速  状态
------------------------------------------------------------------------------------------------
0  源石虫·α        B2     1050/1050   ████████████████████    185     0     0  1.00    100  存活
1  源石虫·α        B2     1050/1050   ████████████████████    185     0     0  1.00    100  存活
...
```

## 文件结构

```
enemy_health/
├── __init__.py          # 包入口 (导出 EnemyReader)
├── __main__.py          # python -m 入口
├── main.py              # CLI 扫描诊断入口
├── memcore.py           # ADB 内存读取底层 (maps/dd/字符串/klass/TcpChannel)
├── memsrv.c             # 设备侧常驻内存服务源码 (zig cc 交叉编译为 bin/memsrv)
├── enemy_reader.py      # 敌人定位(并行bootstrap) + 轮询(poll_fast/poll)
├── enemy_db.py          # enemy_handbook_table 解析 (ID->中文名/编号/描述)
├── game_structs.py      # IL2CPP 结构偏移定义 (全部实测验证)
└── README.md            # 本文件
```

展示层已迁至：

```text
backend/app/enemy_ui.py                # 表格列、精度设置、详情窗口
backend/app/enemy_buff_descriptions.py # Buff/GlobalBuff 中文说明
```

## 地址发现流程（bootstrap）

1. 在设备侧搜索 `Torappu.Battle.BattleController` 类名、Il2CppClass 和当前对象
2. 用状态、倍速、战斗时间和 Unity `m_CachedPtr` 排除已销毁的旧关卡对象
3. 沿 `BattleController+0x2B8 → UnitManager+0x20 → UnorderedArray<Enemy>` 取得完整实时列表；Scheduler 列表保留作兜底
4. 沿 `BattleController+0x158 → LevelData+0x80 → waves` 展开有效 SPAWN 动作
5. 轮询时把当前实例绑定到计划项：未生成=`未出场`，存在=`场上`，消失=`已离场`
6. 固定 waves 之外的条件分支、召唤或插件动态敌人，在首次成为实例时追加到末尾

若主路径因版本字段漂移失败，才执行原有 `enemy_` 字符串 + HP 定点数签名的五阶段
全堆特征扫描兜底。

## 关键偏移 (2.7.51 实测)

| 字段 | 偏移 | 说明 |
|------|------|------|
| Entity.m_hp | 0x40 | FP 当前血量 |
| Entity.m_es / m_epArray | 0x48 / 0x80 | 元素护盾 / 六槽 FP 损伤剩余容量数组 |
| Entity.m_attributes | 0x98 | Attributes* |
| Entity.m_stateMachine | 0x38 | currentStateId 位于 StateMachine+0x48 |
| Entity.buffContainer | 0x150 | 当前活跃 Buff 双缓冲列表 |
| Entity.<id> | 0x130 | 敌人 ID 字符串 |
| Enemy.m_currentTile | 0x320 | Tile*（dump.cs 偏移，待验证） |
| Enemy.m_blockPosition | 0x3C0 | Vector2 float 阻挡位置（待验证） |
| Enemy.m_posInLastFrame | 0x3D0 | Vector2 float 地图坐标（待验证） |
| Enemy.m_routeSpawnPosition | 0x478 | GridPosition (row,col) 出生格（待验证） |
| Attributes.m_cachedData | 0x50 | ObscuredFP[] (步长 0x28, XOR 解密) |
| Attributes 状态/免疫/反制计数 | 0x20 / 0x28 / 0x30 | short[45] |
| List._items / _size | 0x10 / 0x18 | |
| BattleController.Scheduler / LevelData | 0x30 / 0x158 | 当前调度器 / 当前关卡数据 |
| Scheduler.m_spawnedEnemiesCnt | 0x24 | 本局已生成敌人数 |
| Scheduler.m_managedWaveEnemies | 0xC0 | 固定调度器管理的 `List<Enemy>`（兜底） |
| BattleController.unitManager / UnitManager.enemies | 0x2B8 / 0x20 | 全部实时敌人，含运行时召唤 |
| UnorderedArray.items / count | 0x10 / 0x20 | 仅数组前 count 项有效 |
| LevelData.waves | 0x80 | 开局固定 Wave/Fragment/SPAWN 序列 |
| BattleController state/speed/timeScale/playTime | 0x220/0x228/0x280/0x284 | dump.cs 旧偏移已失效 |
| BattleController.m_globalBuffs | 0x68 | List<GlobalBuff>，含目标映射与 Blackboard |
| Enemy.attackWrapper / combatWrapper | 0x550 / 0x558 | dump.cs 一致；combatAbilityPicked 从写入到施放仅约 1 逻辑帧，轮询基本捕不到 |
| EnemySkill._trigger / maxTriggerTime / triggerCnt | 0x20 / 0x2C / 0x40 | 目标触发器指针（NULL=就绪即放）/ 最多触发次数 / 已触发次数 |
| EnemySkill.cooldownTimer / data | 0x48 / 0x80 | PeriodicTimer / ESkillData 静态配置 |
| EnemySkill.checkParentActive / ignoreSilence / m_spCost | 0x28 / 0x38 / 0x3C | 父模式、沉默与运行时 SP 可用性门槛 |
| UnitMode.attackTrigger | 0x48 | 普通攻击的原始 TargetTrigger（目标搜索依据） |
| SelectorTrigger.minTargetNum / lastTarget | 0x24 / 0x38 | 最少目标数 / 当前选择器缓存目标 |
| ESkillData.priority / spCost | 0x18 / 0x24 | 技能优先级 / 静态 SP 消耗 |

下一动作只在游戏真正写入 `CombatWrapper.m_pickedAbility`（或 Spine 已排队下一段
动画）时标记为“确定”。`AttackWrapper` 没有独立 next 槽；游戏尚未决定时，界面会
按反汇编得到的原始规则计算：MoveState 先检查阻挡（COMBAT），否则进入 ATTACK
目标搜索；`Wrapper._PickAbility` 在检查 family/可用性之前锁定 `m_skills` 的最高
priority 组，然后逐项检查启用、CD、触发次数、父 UnitMode、沉默、SP、family 与
TargetTrigger。该组全部失败才回退普通攻击/基础战斗能力；同优先级有多个通过项时，
客户端会使用战斗 RNG 随机择一，不是取列表首项，也不是取 CD 最短项。

读取器不会直接调用游戏的 `TargetTrigger.Search`，因为该函数可能刷新目标、消费随机
数或触发关卡分支。`AlwaysTrigger`、`NeverTrigger`、Selector 已缓存有效目标以及
SpTrigger 的数值比较可以直接按字段求值；LevelBranch、Lua 条件和“空目标后的下一次
搜索”会显示为“规则待判”。因此“规则计算”表示当前只读快照下原始判据得到唯一结果，
“规则随机”表示原始规则得到同优先级候选组，“规则待判”表示仍需游戏执行有副作用的
Search/关卡逻辑；三者都与“游戏已写入”严格区分。

未出场倒计时区分“Scheduler 创建实体”和“玩家看到敌人进入地图”。路线常从地图外
坐标创建（例如列 11），再走到首个 MOVE 路线点（例如列 9）；现在用关卡 RouteData、
敌人静态 moveSpeed（ACTk v2 ObscuredFloat 解密）和 delayToBorn 把这段 3–5 秒预行走
计入“距离出场”，实体已创建但尚未到达首个路线点时仍显示为“未出场”。

属性索引： MAX_HP=0 ATK=1 DEF=2 RES=3 MOVE_SPEED=6 ATTACK_SPEED=7

敌人名称来自 `data/tables/enemy_handbook_table*.bin`（约 1630 条）。

## 游戏更新后的通用修复流程

游戏更新后如果新敌人显示为 ID、血量上限/攻防法抗均为 0，通常分别对应两类数据：

- `Ark_data/dump.cs` 决定运行时对象字段偏移，用来修复血量、属性、状态、Buff 和技能 CD。
- `enemy_handbook_table` 决定跨关卡静态中文名；它不在 Il2CppDumper 输出中，必须从新版游戏 AB 另行解包。

把新版 Il2CppDumper 输出放进 `Ark_data/` 后，在仓库根目录执行：

```bash
python -m tools.enemy_health.update_from_unpack --ark-data Ark_data
python -m unittest tools.enemy_health.test_enemy_health backend.test_enemy_ui -q
```

第一条命令会从 `dump.cs` 生成 `tools/enemy_health/generated_offsets.json`，程序启动时会自动加载；同时会尝试在 `data/anon/` 和 `Ark_data/` 中寻找已经解出的敌人表。

要完整更新未出场敌人的静态名称，推荐用 AssetStudio-Arknights 解出新版 anon AB，然后执行：

```bash
python -m tools.enemy_health.update_from_unpack \
  --ark-data Ark_data \
  --assets "D:/path/to/AssetStudio-output"
```

脚本会提取 `enemy_handbook_table*.bin`、`enemy_database*.bin`，并生成 `data/tables/enemy_names.json`。也可对 UnityPy 能直接读取的原始 AB 使用 `--ab-dir`。仅检查、不写文件时加 `--check`。

ArknightsStudioCLI 的 `exportRaw` 模式会把 TextAsset 导出为 `.dat`；更新脚本会自动识别 `.dat`、`.bin` 和 `.bytes`，复制进 `data/tables` 时统一保存为 `.bin`。

即使静态图鉴表暂时没更新，扫描器也会从场上 `Enemy.data` 获取已生成新敌人的中文名；新版图鉴表用于让同关未出场敌人和离线打包数据库在生成前就有名称。若脚本提示 handbook 早于 `dump.cs`，说明当前仍是旧表，不能把“解析成功”误当作“已经更新”。

## 已知限制

1. **需要 adb root** 读取 `/proc/<pid>/mem`；仅截图正常不能证明内存读取权限正常
2. **MuMu 窗口失去焦点/最小化时游戏会暂停**，此时数值冻结属正常现象
   （是模拟器行为，不是工具问题）；恢复前台后立即继续更新
3. **换关卡/重启游戏后需 `--rebuild`**（Boehm GC 地址随战斗重建）
4. 固定 waves 之外的显式分支和未使用敌人引用会预列为“条件触发/潜在召唤”；
   重复技能召唤次数、插件动态内容及其绝对时刻无法在开局确定，实际出现后会自动追加并继续追踪生命周期
