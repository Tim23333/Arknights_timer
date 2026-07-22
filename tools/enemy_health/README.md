# 明日方舟敌人血量/属性实时监控工具

通过 ADB 读取 MuMu 模拟器中游戏进程内存，实时获取战斗中每个敌人的
名称、血量、攻击/防御/法抗/移速/攻速等详细数据。

## 原理

```
MuMu 模拟器 (Android)
  └── 明日方舟进程 (IL2CPP, arm64)
       └── Scheduler.m_managedWaveEnemies (List<Enemy>)
            └── Enemy: m_hp / <id> / Attributes.m_cachedData
```

首次运行通过内容特征在 GC 堆中定位敌人列表（多路 adb 并行扫描，约 3-7 分钟），
地址链缓存到 `enemy_cache.pkl`，之后秒级启动。

轮询分两档：
- **准实时 `poll_fast()`**（GUI/CLI 默认）：常驻 TCP 通道（`adb forward tcp:27271`）。
  通道有两种模式，自动探测：
  - **memsrv 模式（默认，~2-5ms/帧）**：`memsrv.c` 交叉编译出的 aarch64 静态
    小程序（`bin/memsrv`），由 `nc -L` 以 socket 为 stdin/stdout 启动，
    打开 `/proc/<pid>/mem` 一次后每次读取仅一个 pread 系统调用。协议为
    小端二进制（横幅 `AKMSRV1\n`；请求 `u64 N + N×{addr,size}`；响应
    `i64 n + data`，n<0 为 -errno）。
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
3. **Python 3.8+**，依赖 `numpy`（扫描加速）；GUI 需 `PySide6`

## 使用方法

### 图形界面 (推荐)

```bash
python -m tools.enemy_health.gui
# 或
python -m tools.enemy_health --gui
```

- 启动后自动尝试缓存地址秒级进入监控
- **一键扫描**: 全堆扫描重新定位 (多路 adb 并行, 约 3-7 分钟)
- 表格准实时展示 (默认 0.03 秒刷新, 可调至 0.02): 名称/编号/ID/坐标/血条/攻击/防御/法抗/移速/攻速/状态
- 状态栏显示每帧读取耗时 (ms/帧)

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
├── gui.py               # PySide6 图形界面 (一键扫描+实时监控)
├── main.py              # CLI 监控界面
├── memcore.py           # ADB 内存读取底层 (maps/dd/字符串/klass/TcpChannel)
├── memsrv.c             # 设备侧常驻内存服务源码 (zig cc 交叉编译为 bin/memsrv)
├── enemy_reader.py      # 敌人定位(并行bootstrap) + 轮询(poll_fast/poll)
├── enemy_db.py          # enemy_handbook_table 解析 (ID->中文名/编号/描述)
├── game_structs.py      # IL2CPP 结构偏移定义 (全部实测验证)
└── README.md            # 本文件
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
| Entity.m_attributes | 0x98 | Attributes* |
| Entity.<id> | 0x130 | 敌人 ID 字符串 |
| Enemy.m_currentTile | 0x320 | Tile*（dump.cs 偏移，待验证） |
| Enemy.m_blockPosition | 0x3C0 | Vector2 float 阻挡位置（待验证） |
| Enemy.m_posInLastFrame | 0x3D0 | Vector2 float 地图坐标（待验证） |
| Enemy.m_routeSpawnPosition | 0x478 | GridPosition (row,col) 出生格（待验证） |
| Attributes.m_cachedData | 0x50 | ObscuredFP[] (步长 0x28, XOR 解密) |
| List._items / _size | 0x10 / 0x18 | |
| Scheduler.m_managedWaveEnemies | 0xB8 | List<Enemy> |
| BattleController state/speed/timeScale/playTime | 0x220/0x228/0x280/0x284 | dump.cs 旧偏移已失效 |

属性索引： MAX_HP=0 ATK=1 DEF=2 RES=3 MOVE_SPEED=6 ATTACK_SPEED=7

敌人名称来自 `data/tables/enemy_handbook_table*.bin`（约 1630 条）。

## 已知限制

1. **需要 adb root** 读取 `/proc/<pid>/mem`（MuMu 默认支持）
2. **MuMu 窗口失去焦点/最小化时游戏会暂停**，此时数值冻结属正常现象
   （是模拟器行为，不是工具问题）；恢复前台后立即继续更新
3. **换关卡/重启游戏后需 `--rebuild`**（Boehm GC 地址随战斗重建）
4. **Bootstrap 较慢**（约 3-7 分钟并行扫描，结果缓存磁盘）
