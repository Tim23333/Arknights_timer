# 明日方舟敌人内存扫描模块

通过 ADB 读取 MuMu 模拟器中游戏进程内存，实时获取战斗中每个敌人的
名称、血量、攻击/防御/法抗/移速/攻速等详细数据。

## 原理

```
MuMu 模拟器 (Android)
  └── 明日方舟进程 (IL2CPP, arm64)
       └── Scheduler.m_managedWaveEnemies (List<Enemy>)
            └── Enemy: m_hp / <id> / Attributes.m_cachedData
```

首次运行通过内容特征在 GC 堆中定位敌人列表（多路 adb 并行扫描，约 1-3 分钟），
地址链缓存到 `enemy_cache.pkl`，之后秒级启动。扫描共 5 个阶段，但只有第 1 阶段
走网络传输——扫描块同时落盘为临时快照（IL2CPP Boehm GC 不移动对象，快照窗口内
地址稳定），后 4 个阶段全部从本地磁盘重放，把 adb 隧道传输量从 5 份堆压到 1 份；
候选实体的 klass 验证逐个走 `adb exec-out` 小读。

> **大块读取注意（2026-07-22 修复）**：`dd` 大块读取必须头/尾 4KB 页对齐、
> 中部整 4MB 块——若把起点/终点 4MB 对齐到区域外的未映射洞，`dd` 直接 EIO
> 导致整块 32MB 丢失（确定性，非偶发）。此前扫描时灵时不灵，根因就是关键
> 对象所在区域起点前恰好有/没有洞。扫描结束若丢块会打印警告。

轮询分两档：
- **准实时 `poll_fast()`**（后端主程序/CLI 默认）：常驻 TCP 通道（`adb forward tcp:27271`）。
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
  List 头每 4 帧读一次（靠 `List._version` 检测列表修改，含同数量替换，
  变化才重读 items 并重新聚簇）；属性每 3 帧轮换刷新 1 个敌人，摊平尖峰；
  BattleController 块每 10 帧读一次；新刷敌人在通道内 2 批解析
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

1. **MuMu 模拟器** 已启动，明日方舟已进入战斗关卡且场上有敌人
2. **adb root** 可用（MuMu 自带 adb 默认支持，工具自动查找路径）
3. **Python 3.8+**，依赖 `numpy`（扫描加速）

## 使用方法

### 后端主程序页面

```bash
cd backend
python run.py
```

- `tools/enemy_health` 不再维护独立 GUI；页面统一由 `backend/desktop_app.py` 承担
- 主程序启动后可尝试缓存地址秒级进入监控
- **一键扫描**: 全堆扫描重新定位 (多路 adb 并行, 约 1-3 分钟)
- 表格准实时展示 (默认 0.016 秒刷新=60Hz, 可调至 0.008): 名称/编号/ID/坐标/血条/攻击/防御/法抗/移速/攻速/状态
- **显示列**可逐项勾选全部最终属性、异常状态、状态免疫、护盾，以及神经/侵蚀/灼燃/凋亡/狂躁五类损伤条；选择会持久化
- 每行的**详情**按钮按需读取原始/最终属性、45 项状态与免疫计数、当前 Buff、关卡全局 Buff、技能和精确损伤条，不增加常态轮询负担
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

# 指定 adb 路径 / 刷新间隔
python -m tools.enemy_health --adb "D:\...\adb.exe" --interval 1
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

## 地址发现流程 (bootstrap)

1. 扫 GC 堆找 `"enemy_"` UTF-16 字符串对象集合 S
2. 扫 HP 签名（FP Q32.32 整数血量：低 32 位=0，高 32 位=HP）位置 P
3. 扫指向 S 的指针位置集合 R；候选实体 B=P-0x40，若 B+0x100..0x1A8
   内有位置 ∈ R 且 klass 名 == `'Enemy'` → 场上敌人
4. 扫指向敌人的指针 → items 数组 → `List<Enemy>` 候选（可能含快照拷贝列表）
5. 单遍扫描指向所有 List 候选的指针 → 候选中持有者经 `SchedulerDriver`
   验证为真 Scheduler 的才是真 `m_managedWaveEnemies`；
   SchedulerDriver +0x10 → BattleController（状态/倍速/时间）

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
| Scheduler.m_managedWaveEnemies | 0xB8 | List<Enemy> |
| BattleController state/speed/timeScale/playTime | 0x220/0x228/0x280/0x284 | dump.cs 旧偏移已失效 |
| BattleController.m_globalBuffs | 0x68 | List<GlobalBuff>，含目标映射与 Blackboard |

属性索引： MAX_HP=0 ATK=1 DEF=2 RES=3 MOVE_SPEED=6 ATTACK_SPEED=7

敌人名称来自 `data/tables/enemy_handbook_table*.bin`（约 1630 条）。

## 已知限制

1. **需要 adb root** 读取 `/proc/<pid>/mem`（MuMu 默认支持）
2. **MuMu 窗口失去焦点/最小化时游戏会暂停**，此时数值冻结属正常现象
   （是模拟器行为，不是工具问题）；恢复前台后立即继续更新
3. **换关卡/重启游戏后需 `--rebuild`**（Boehm GC 地址随战斗重建）
4. **Bootstrap 较慢**（约 1-3 分钟并行扫描，结果缓存磁盘）
