# V2 通用底座实现与运行

2026-10-05 当前生产底座为 **f0c294**，包含逐格地图场域与拥有能力的冷却／中断协议，共106项计算契约。
同版本1219项完整回归、0-1／自定义公式基线、25项作者检查和17项联合独立门已实际通过后推广九文件。
接口与身份比较限定见 [逐格地图与技能时钟](campaign/CHAPTER09_CHANNEL_MAP.md)，全程进度见 [当前状态](campaign/CURRENT_STATUS.md)。

以下71d33f及更早段落保留历史身份。71d33f在20e通用机制基础上增加只读子树与当前弹道记录读写。
它自己的1219项完整回归、0-1基线及独立四项／三组精确配对比较全部通过。
收据见 [弹道子记录推广](../validation/campaign/chapter08_projectile_leaf_v1_primary/promotion.json)，
性能与逐值范围见 [验证说明](campaign/PROJECTILE_LEAF_CANDIDATE.md)。

2026-10-04 最新主底座为 **20e812**，已新增可替换动态 Buff 寿命、真实复活自持 Buff、有界预定义实例复用、零HP有限终末阶段与当前回调资格隔离。它自己的1219项完整回归、标准0-1／自定义公式基线和25项独立联动检查全部实际通过，精确14文件推广；101个源码与catalog文件和固定候选字节相同。收据见 [联合源码推广](../validation/campaign/chapter08_joint_v4_primary/promotion.json)，配置见 [联合机制](campaign/CHAPTER08_JOINT_V2.md) 和 [终末权限修复](campaign/CHAPTER08_TERMINAL_JOINT_V4.md)。旧9ad完整备份保留，下面9ad段落为当时历史状态。

本次完整套件只把旧“恰好98个契约”检查更新为精确旧98项加 `buff.lifetime_rate` 及不可变性验证，其余1218项原断言不变。为保留其他在途验证的源码guard，旧 `tests_v2/test_rules.py` 字节暂不更新；新版完整门使用 `tools/chapter08_joint_v2/run_full_suite_v2.py`，传入当前runtime-root与expected-core，旧数量失败历史保留。完整Boss、循环机关时间策略、下一波跟踪和整关仍分别推进，见 [当前持续目标](campaign/CURRENT_STATUS.md)。

V2 独立运行时已写入 `ark_sim`。内容编译、规则计算、状态执行和作者工具均由新版模块完成；新运行路径不导入阶段一 `ark_emulator` 的战斗、技能、Buff、地图、波次或随机数实现。本文描述当前实际实现，架构蓝图见 [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)。

2026-10-04 主底座为9ad987，包含显式有限状态机重启和纯目标查询的time／seconds／quantum上下文，保留3992的共享光环、复活等待期动作、真实地形资格、边界缓存、当前波次请求、卡片、自定义范围实时投影及公开运动同步。它自己的1219项完整回归、标准0-1／自定义公式基线和17项独立边界检查均实际通过后，精确8文件推广，收据见 [源码推广](../validation/campaign/chapter08_restart_clock_primary/promotion.json)。旧3992完整备份保留；动态Buff寿命和复生自身Buff候选尚未推广。实际状态见 [当前持续目标](campaign/CURRENT_STATUS.md)，接口见 [重启设计与验证](campaign/BEHAVIOR_RESTART_DESIGN.md)。

当前证据是模型验证，尚未采集新的真实客户端逐帧对照。自定义合成场景已验证组成技能与规则切换；0-1 使用独立 V2 内容和同一个底座，首关验证结果与待校准项分别记录。

下列M68及测试数字为历史基线快照；当前身份及最新通过证据以顶部说明和持续目标状态为准。
M68 当时的主目录源码为 `1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8`，含92项计算契约。
新增显隐与资格投影、地块接触、领域范围、障碍、显式原路线连通性、部署／退场冷却和库存支付等接口。
冻结候选完整1565项及独立部署21项通过；主目录源码逐字节一致，三个内容包身份重建及38项规则测试通过。
主目录0-1完整基线已actualexit0通过：11击杀／0漏怪，181937条完整事件与磁盘检查点、开局回放精确相等；自定义公式850／60通过。
推广记录见 [源码推广](../validation/campaign/m68_primary/promotion.json)，当前运行证据见 [主目录基线](../validation/campaign/m68_primary/baseline.json)。
以下首次/M1/M2及其他阶段结果保持各自历史身份。最新输入和未完成范围见 [当前状态](campaign/CURRENT_STATUS.md)。

## 2026-10-02 首次 V2 验收结果

独立 V2 测试 **332 项全部通过，耗时 7.79 秒**，包含编译预检、公式、事务、资源、技能、Buff、初始内容、时序、只读隔离、随机数、身份锁和回放。运行日志与源码摘要见 [测试证据](../ark_sim/validation/reports/v2_tests_20261002.json) 和 [原始日志](../ark_sim/validation/reports/v2_tests_20261002.log)。

0-1 固定夜刀 30 级、克洛丝 40 级，精零、技能 1 级，在逻辑时间 0 和 180 分别部署。新底座完成 **11 击杀、0 漏怪、全部波次清空**，在逻辑时间 2408 判定 victory，即模型时间约 80.267 秒。运行继续到 2550 以固定检查终点。

连续运行、从时间 300 的检查点恢复续跑、从头执行输入回放，最终 World、任务队列、随机状态、时钟与 **172,804 条事件**的精确 SHA-256 摘要均一致，未使用数值容差。完整输入与校验范围见 [模型验收记录](../ark_sim/validation/reports/v2_baseline_20261002.json) 和 [版本锁定回放](../ark_sim/validation/reports/v2_baseline_20261002.replay.json)。

首关的该结果为 `model_validated`；客户端逐帧准确性仍为 `pending`。原生出生偏移、移动 steering、动作命中帧、教程控制和 RNG 调用序列需分别校准。大量完整计算日志仍有明显运行与内存开销，当前首关用来验证底座与组合机制。

可以重新生成验收证据：

```powershell
..\.venv\Scripts\python.exe tools/verify_v2_baseline.py
```

脚本先验证自定义场景的两套数值规则，再运行完整首关、检查点续跑和输入回放。公式或源码变化后，旧记录会被拒绝；应重新生成证据，不能保留旧通过状态作为新版本结果。

## 主线回归基础版本（M1）

固定十二人、36个标准主线尾关的持续目标见 [campaign/GOAL.md](campaign/GOAL.md)。
本阶段实际修复行为计划未生效、按攻击 SP 被按目标/命中重复回复，以及未实现的运动模式、控制检查点和特殊瓦片被静默接受的问题。
飞行、传送、特殊地板等目前明确拒绝，仍待领域实现；未把拒绝门称为机制已实现。

当前441项V2测试通过，0-1重新完成11击杀、零漏怪；连续、检查点续跑和完整回放的状态与181,590条事件摘要精确一致。
新证据保存于 [foundation_baseline_20261002.json](../validation/campaign/foundation_baseline_20261002.json)
和 [foundation_tests_20261002.json](../validation/campaign/foundation_tests_20261002.json)。
此前首轮证据的源码身份保持原样；它不代表本阶段新增源码的当前通过结果。

## 当前单位与原语版本（M2）

最新实现与边界见 [M2_PROGRESS.md](campaign/M2_PROGRESS.md)。530项全V2测试通过；标准12人输入规范化、桃金娘S2组合原型、事件资源与通用飞行已接入。
飞行沿声明路径点直线移动并忽略地面阻挡，地面保持BFS；其他未实现特殊地板和控制类型仍拒绝。
新身份0-1的181,638条事件及检查点/完整回放精确一致，证据见 [m2_baseline_20261002.json](../validation/campaign/m2_baseline_20261002.json)。
正式主线验收仍为0/36，不能把原型或数据规范化提升为12人完整运行。

## 快速运行

在 `D:\Arknights\Arknights_timer\Ark_emulator` 目录运行：

```powershell
# 检查内容、规则、能力与引用
..\.venv\Scripts\python.exe -m ark_sim validate packages/custom/custom_guard.json

# 同一份单位与技能内容，采用两套不同规则集
..\.venv\Scripts\python.exe -m ark_sim run packages/custom/custom_guard.json --ruleset ruleset/ark_standard --seconds 1 --output sandbox_standard.json --replay-output sandbox_replay.json
..\.venv\Scripts\python.exe -m ark_sim run packages/custom/custom_guard.json --ruleset ruleset/custom_balance --seconds 1 --output sandbox_balanced.json

# 官方首关的独立V2内容与固定部署输入
..\.venv\Scripts\python.exe -m ark_sim validate packages/ark_content/level_main_00_01.json
..\.venv\Scripts\python.exe -m ark_sim run packages/ark_content/level_main_00_01.json --commands scenarios/level_main_00_01/commands.json --ticks 3000 --output ark_00_01.json --replay-output ark_00_01_replay.json
```

CLI 的 validate、explain、preview、run、replay 均实际调用新编译器或运行时。`--output` 保存 JSON；省略时打印结果。长程运行建议保存结果，避免在终端打印完整事件轨迹。`replay --record` 使用记录中的种子、时间和身份，不允许另外修改。

## 自定义内容的真实结果

样例定义一个没有官方 ID 限制的单位，拥有 HP 和 energy、普通攻击及三段技能。技能支付 20 energy、增加 50% 攻击、执行三次命中，并按被接受的目标命中返还 2 energy。

| 配置 | 一秒模型结果 | 独立预期 |
|---|---|---|
| 标准规则集 | 伤害 850，靶子 HP 9150，energy 约 8 | 三段各 260、一次普攻 70；支付后返还 6、恢复 2 |
| custom_balance | 伤害 60 | 整条伤害管线替换为每次有效攻击力的 10%，跳过默认减伤 |

两套运行使用同一份场景、单位、技能和操作。更换规则或参数会改变程序指纹，结果变化不需要编辑内核。

## Python API

```python
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference

program = Compiler().compile(
    "packages/custom/custom_guard.json",
    ruleset="ruleset/ark_standard",
)
simulation = Engine.create(program, seed=123)
simulation.advance(30)
snapshot = simulation.snapshot()
record = simulation.export_replay()
restored = replay(program, record)
assert first_difference(snapshot, restored.snapshot()) is None

checkpoint = simulation.checkpoint()
continued = Engine.restore(program, checkpoint)
continued.advance(30)
```

逻辑时间单位由规则集 quantum 决定，不把秒数直接等同固定帧数。运行时没有额外实时线程；暂停对应不推进 Session，单步与批次推进由调用者控制。

## 实际模块边界

| 层 | 实现 |
|---|---|
| kernel | 任意组件 World、本地实体与事件 ID、任务顺序、原子事务与嵌套 savepoint、检查点、可注入命名随机数算法 |
| rules | 92 项命名契约、安全表达式、动态作用域、计算图、数值 profile、纯提供器与子计算服务、详细计算轨迹 |
| content | JSON 与 Builder 共用编译、继承与覆盖、传递依赖、字段与能力预检、不可变 Program、提供器及规则版本锁 |
| domains | 有效属性与成长、任意资源、技能与效果、Buff、状态图、选择器、空间、生命周期 |
| presets | 明日方舟的公式、属性层、部署、目标排序和生命周期规则，允许用户替换 |
| adapters 与 tools | Engine API、离线数据转换、CLI、回放、首次差异比较 |

固定十二人主线回归的最新内容、通用接口与同身份验证见 [M6进展](campaign/M6_PROGRESS.md)。
其0-10可执行包仍是partial集成模型，正式36关验收状态单独记录。
空间、容量、转向及首章全程推进的后续实现见 [M7进展](campaign/M7_PROGRESS.md)；旧身份验证保留历史。
动态波次、截止时钟、不可变日志共享与最新验证见 [M8进展](campaign/M8_PROGRESS.md)。

公式和算法按计算 ID 调用。属性支持整个管线和单属性规则，资源支持局部容量、成本、恢复和边界规则，伤害支持整体计算图及其子阶段覆盖。纯提供器可以委托子计算，轨迹保留实际绑定和中间值，没有 World 写入口。

## 时间与资源

资源可以连续恢复，也可以声明周期驱动：

```json
{
  "initial": 10,
  "capacity": 99,
  "recovery_rate": 1,
  "recovery": {"mode": "periodic", "interval_seconds": 1}
}
```

驱动只决定何时调用 resource.recovery，具体数值仍由规则计算。整数计时避免周期回复的累积误差；显式暂停条件保留剩余时间。满容量的自定义冷却规则仍执行，不被假设为正向恢复。

0-1 的 DP/SP 声明每秒周期回复；自定义 energy 可连续恢复。SP 仅在声明的施放模式下停止回复，普通攻击不被一概冻结。

## 原子性与回放

命令、能力启动与资源支付会进入 Session.atomic 或同批意图提交。后续创建失败、别名冲突、规则异常和无效任务会回滚实体、资源、事件、任务、ID 与随机数消耗。失败结果单独记录，不留下部分部署或支付。

回放保存执行时间和提交时间，支持在推进后追加未来命令；检查点保存完整状态及排队任务，恢复前重新注册实现。内容、规则、提供器、随机算法与实现身份不一致时，恢复或回放明确拒绝。

```powershell
..\.venv\Scripts\python.exe -m ark_sim replay packages/custom/custom_guard.json --record sandbox_replay.json --output sandbox_replayed.json
```

使用外部 Python 提供器时，其参数和版本应写入注册声明。提供器须只根据输入、参数和只读计算上下文返回结果；捕获外部可变状态会破坏这一纯计算约定。改算法时同时修改声明版本并重新编译。

随机算法可通过 random_factory 或 random_registry 注入。默认算法是命名 MT19937 流，其模型证据不代表已复刻当前游戏 RNG。复放外部提供器或随机后端时，需要传入相同实现和版本。

## 调试轨迹与内存

默认使用 compact 轨迹，保留实际输入、参数、中间值、结果、规则指纹和关联实体 ID，避免反复嵌入完整上下文及施放历史快照。规则集 parameters.trace_mode 可设为 full 进行短程详细调试。

同一个逻辑时间内，相同不可变视图和相同规则作用域的属性求值可以复用结果，命中发布 calculation.cached 并指向原始计算事件。实体修改、时间推进、检查点恢复或事务回滚会使相关缓存失效。缓存不包含在持久状态中，也不能跨历史快照或作用域共享。

完整 World 与 checkpoint 不裁剪。能力取值快照保存属性、资源、位置和状态，只排除施放快照内的历史快照副本，避免双方攻击互相包裹旧视图而无界增长。默认 compact 与完整调试模式的日志内容不同，比较证据必须固定模式。

## 当前明确限制

已有技能可由通用原语组合，常见 Buff 支持周期、订阅、叠层和清理；复杂新原语需要扩展领域契约与实现。不能把契约存在解释为全部游戏机制已实现。

当前明确拒绝未实现的实际动态定义引用、完整装备/全角色养成转换、嵌套状态子图、自定义 Buff 叠层提供器、中断退款或继续执行策略、连续刚体碰撞，以及单个修饰器的 rule/operation 字段。位移/push/距离账本、声明式路线与资源精确控制已有通用模型。属性整体或单层算法仍可通过规则替换。支持浮点数值后端，其他后端明确报错。

空间默认使用四邻域安全路径，原生对角 steering、敌人命中帧、出生随机偏移和教程控制时序尚待客户端证据校准。新增关卡只提升通过对应验收的组合。

## 验证与扩展

```powershell
..\.venv\Scripts\python.exe tools/run_primary_v2_suite.py
```

当前完整入口明确更新一项历史 catalog 数量期待：精确保留原 98 个契约，新增
`buff.lifetime_rate` 的字段和不可变性检查，其余 1218 项原断言保持不变。
测试包含独立公式预期、整个规则集切换、属性与资源局部绑定、成长、自定义随机数、事务、事件预算、技能中断、快照隔离、交互回放与身份锁、Schema 和 CLI。最新数量与首关证据见 validation/reports 下的记录。

新增内容通常只修改 packages 下的 JSON；新增算法先注册纯提供器，再编译它的类型与依赖，最后补独立预期和场景对照。作者字段与 Builder 示例见 [V2_AUTHORING.md](V2_AUTHORING.md)。
