# ArkSim 通用模拟底座

项目的主入口是独立 V2 包 **`ark_sim`**。单位、干员、敌人、技能、Buff 和状态图通过内容定义组合；属性、资源、伤害、时间、空间与结算通过规则集、表达式、计算图和提供器执行。明日方舟作为一个可替换预设接入，内容覆盖按关卡推进，首个官方基线为 **0-1**。

V2 已有可运行的内容编译器、通用内核、领域系统、规则运行时、Python API 和 CLI。新的执行路径不导入旧 `ark_emulator` 的战斗、技能、Buff、地图、波次或随机数实现。离线导入器可以读取既有 JSON 提取产物。

当前证据属于模型验证。2026-10-02 的 V2 测试 332 项全部通过；0-1 两人模型已 11 击杀、零漏怪清场，并通过检查点续跑与完整事件回放。真实客户端的命中帧、移动、出生偏移、教程时序等仍需对照；内容导入、内部测试和确定回放不等同于全游戏完整还原。

- [V2 实际实现与运行](docs/V2_IMPLEMENTATION.md)
- [内容、规则、Builder 与 CLI 作者指南](docs/V2_AUTHORING.md)
- [当前需求](docs/REQUIREMENTS.md)
- [固定十二人主线回归持续目标](docs/campaign/GOAL.md)
- [V2 架构设计](docs/ARCHITECTURE_V2.md)
- [全部文档索引](docs/README.md)

## 快速运行 V2

以下命令使用项目已有的 Python 环境，在模拟器目录执行：

```powershell
cd D:\Arknights\Arknights_timer\Ark_emulator

# 检查内容、规则、引用、提供器与实际需要的计算接口
..\.venv\Scripts\python.exe -m ark_sim validate packages/custom/custom_guard.json

# 查看加载的依赖与全局、场景和局部规则
..\.venv\Scripts\python.exe -m ark_sim explain packages/custom/custom_guard.json --output dependencies.json

# 运行同一内容，并导出快照与输入回放
..\.venv\Scripts\python.exe -m ark_sim run packages/custom/custom_guard.json --seconds 1 --output sandbox_standard.json --replay-output sandbox_replay.json

# 切换整条伤害计算管线，继续使用相同单位、技能与场景
..\.venv\Scripts\python.exe -m ark_sim run packages/custom/custom_guard.json --ruleset ruleset/custom_balance --seconds 1 --output sandbox_balanced.json

# 使用记录里的种子、时间、命令和身份重放
..\.venv\Scripts\python.exe -m ark_sim replay packages/custom/custom_guard.json --record sandbox_replay.json --output sandbox_replayed.json
```

CLI 提供 `validate`、`explain`、`preview`、`run`、`replay`。`--output` 保存 JSON，省略时打印结果。`run --ticks` 推进整数逻辑时间，`--seconds` 通过所选 `time.quantize` 计算规则换算；规则集的 `quantum` 决定逻辑时间单位。`replay` 必须提供 `--record`，不能额外更改种子或终点。参数详情可用 `python -m ark_sim --help` 和各子命令的 `--help` 查看。

`preview` 的输入可使用 JSON 文件。例如将以下内容保存为 `inputs.json`：

```json
{"power": 100, "defense": 80, "resistance": 0, "damage_type": "physical"}
```

```powershell
..\.venv\Scripts\python.exe -m ark_sim preview packages/custom/custom_guard.json --rule rule/my_physical --inputs inputs.json
```

0-1 的独立内容包与固定部署操作位于 `packages/ark_content` 和 `scenarios/level_main_00_01`。可以先验证输入或运行短段调试：

```powershell
..\.venv\Scripts\python.exe -m ark_sim validate packages/ark_content/level_main_00_01.json
..\.venv\Scripts\python.exe -m ark_sim run packages/ark_content/level_main_00_01.json --commands scenarios/level_main_00_01/commands.json --ticks 300 --output ark_00_01_preview.json
```

首关的模型验收结果和待校准项以 [V2 实现说明](docs/V2_IMPLEMENTATION.md) 及对应证据为准。运行到某个时间点本身不表示首关完整验收通过。

## Python API 与回放身份

```python
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference

program = Compiler().compile("packages/custom/custom_guard.json")
simulation = Engine.create(program, seed=123)
simulation.advance(30)
snapshot = simulation.snapshot()
record = simulation.export_replay()
restored = replay(program, record)
assert first_difference(snapshot, restored.snapshot()) is None

checkpoint = simulation.checkpoint()
continued = Engine.restore(program, checkpoint)
```

内容、规则、提供器、数值配置、随机算法或实现身份改变后，旧记录会被明确拒绝，应重新编译并生成证据。检查点恢复和首次差异报告见 [V2 实现说明](docs/V2_IMPLEMENTATION.md)。

常见自定义通过修改 JSON 或 Python Builder 完成：任意命名空间 ID 的单位、任意资源、组合技能、Buff、成长、单属性或单资源规则，以及完整计算管线。复杂算法通过独立提供器注册。编译器检查实际依赖和支持能力；没有实现的必需接口会报错，不会切回旧引擎。

## 目录与验证

```text
Ark_emulator/
  ark_sim/
    kernel/       时间、World、任务、事务、事件、随机流和检查点
    contracts/    共享定义、计算结果和变更意图
    rules/        类型契约、表达式、计算图、作用域和数值配置
    content/      内容读取、schema、继承、依赖与编译
    domains/      属性、资源、技能、效果、Buff、行为、空间和生命周期
    presets/      可替换的明日方舟算法
    adapters/     Engine 与离线导入器
    tools/        作者工具、CLI、回放与差异比较
  packages/       自定义内容与转换后的关卡包
  scenarios/      场景操作输入
  tests_v2/       新底座的独立预期与集成验证
  docs/           当前设计、作者指南及历史资料
  ark_emulator/   旧实现与阶段一原型
```

运行时代码使用 Python 标准库，测试使用 `pytest`：

```powershell
..\.venv\Scripts\python.exe tools/run_primary_v2_suite.py
```

当前明确的边界包括完整装备与全角色养成转换、动态引用执行、嵌套状态子图、自定义 Buff 叠层策略、中断退款或继续执行、连续刚体碰撞和其他数值后端。已实现的属性层、资源、效果、力学位移与整条管线可替换，详见 [作者指南](docs/V2_AUTHORING.md)。

## 当前主线回归目标

已启动固定十二人、标准主线各章末两关的持续目标，本地冻结范围为第0–17章、36关。
编队、选择规则、数据恢复和验收门见 [目标说明](docs/campaign/GOAL.md)，
机器进度见 [progress.json](validation/campaign/progress.json)。
当前36关核心原生数据已恢复并精确对照；固定十二人的实际配置、选技、天赋与召唤已部分整合到V2。
正式关卡与完整原生干员通过数仍为0；源、数学模型、整合见证与客户端准确性分别记录。

历史冻结M8核心通过1002项完整测试，0-1保持11击杀零漏怪及检查点/命令回放一致。
0-10原模型已35出生/35击杀/零漏怪，顺序恢复与回放仍在执行；0-11原模型探索已37出生/37击杀/零漏怪，
该次no-replay探索未作正式验收。独立审查发现并修复Saria增伤与Liskam护盾的整合绑定遗漏，
修订内容另有输入身份、定向机制测试和长程运行，旧胜利不迁移成新内容通过。
当前进展见 [M8](docs/campaign/M8_PROGRESS.md)、[整合修复](docs/campaign/M8_DAMAGE_AND_ROSTER_REPAIRS.md)、
[首关验收范围](docs/campaign/FIRST_MODEL_ACCEPTANCE_SCOPE.md) 及 [第1章来源](docs/campaign/CHAPTER01_SOURCE_AUDIT.md)。

当前主目录已推广到M68，源码身份为1761a06d，计算契约92项。新增显隐与资格、地块接触、领域范围、
障碍与原路线连通性、部署／退场冷却策略、库存及精确支付等通用接口，公式和政策均由内容绑定。
冻结候选完整回归1565项及独立部署21项通过；推广前后源码字节与三个编译内容包身份一致。
推广及主目录运行证据见 `validation/campaign/m68_primary/`；旧M10及其他版本记录保留历史身份。
实时状态、各版本输入与已完成/进行中证据见 [CURRENT_STATUS](docs/campaign/CURRENT_STATUS.md)。

基础阶段（M1）修复后的V2测试441项通过，0-1在该实现身份下重新通过完整模型与回放，
当前证据见 [foundation_baseline_20261002.json](validation/campaign/foundation_baseline_20261002.json)。
上文首轮332项/172,804事件记录对应首次V2实现身份，保留为历史版本证据。

历史M2新增标准单位规范化、桃金娘S2原型、事件资源与飞行，530项测试通过，0-1在该身份下保持清场和精确回放。
进展和未完成范围见 [M2_PROGRESS.md](docs/campaign/M2_PROGRESS.md)。

## 历史实现

**V1 已停止作为开发底座。** `ark_emulator`（包括阶段一原型）、`examples/run_modular.py`、`run_web.py`、旧网页、AI 接口与 `tests/` 均标记为历史实现，仅用于离线数据提取和代码、行为样本参考。后续功能、公式修复、干员与关卡扩展、网页和 AI 接入统一基于 V2 `ark_sim`。

历史目录原样保留以便追溯。其运行结果、覆盖数字和模型回放不属于 V2 验收；V2 运行时不调用旧引擎。边界与目录清单见 [V1 历史说明](docs/V1_HISTORY.md)，后续开发约定见 [AGENTS.md](AGENTS.md)。

历史资料见 [模块化原型说明](docs/MODULAR_IMPLEMENTATION.md)、[代码审查与差距评估](docs/SIMULATION_COMPLETENESS_REVIEW.md)、[机制资料](docs/MECHANICS.md) 和 [历史交付审计](docs/DELIVERABLES_AUDIT.md)。外部工具与数据链接见 [参考资料](docs/REFERENCES.md)。
