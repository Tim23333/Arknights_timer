# V2 内容创作与规则配置

当前20e主底座新增的动态寿命、复活自持和预定义复用配置见 [联合机制与例子](campaign/CHAPTER08_JOINT_V2.md)；零HP有限终末阶段与Buff结束回调资格见 [终末权限](campaign/CHAPTER08_TERMINAL_JOINT_V4.md)。这些是通用数据契约，敌人ID和技能数值仍在内容包与可替换规则中定义。

本文对应实际的 `ark_sim` 编译器、规则运行时、Builder 和 CLI。明日方舟预设与内容包独立于时间、实体、调度和事务内核。作者通过定义与规则组合单位，无需添加角色专用 Python 类。

可运行样例为 [packages/custom/custom_guard.json](../packages/custom/custom_guard.json)。架构与需求见 [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) 和 [REQUIREMENTS.md](REQUIREMENTS.md)。规则契约的运行版本随包保存于 `ark_sim/rules/contracts.json`；设计清单中的声明不等于所有游戏机制已实现。

## 先运行作者工具

在 `D:\Arknights\Arknights_timer\Ark_emulator` 执行：

```powershell
..\.venv\Scripts\python.exe -m ark_sim validate packages/custom/custom_guard.json
..\.venv\Scripts\python.exe -m ark_sim explain packages/custom/custom_guard.json --output dependencies.json
.\Run-Simulation.ps1 -Content packages/custom/custom_guard.json -Ticks 30

# 同一内容采用另一整条伤害管线
.\Run-Simulation.ps1 -Content packages/custom/custom_guard.json -Ruleset ruleset/custom_balance -Ticks 30

# 从固定 JSON 提取产物离线转换 0-1，不导入旧模拟运行时
..\.venv\Scripts\python.exe -m ark_sim validate --scenario ark-00-01
```

`validate` 检查结构、引用、传递依赖、继承、循环、计算规则、提供器和实际内容需要的计算接口。错误返回非零退出码，并显示定义 ID 或字段路径。`explain` 输出依赖关系、提供器版本、规则预设、场景和嵌套作用域。`preview` 给出试算值与计算轨迹。`run` 使用真实 Engine，输出快照，可同时导出回放。`replay` 必须提供 `--record`，按记录里的种子、时间、命令与身份重放，不接受额外的种子或时间参数。

`Run-Simulation.ps1` 将此次运行的快照、回放和终端输出统一放入 `E:\ArkSimLogs\runs`，
退出后自动清理并保留精简退出摘要。需要续跑、重放和数值核对时，使用
[受控验证入口](SIMULATION_LOGS.md)，在同一受控任务内完成比较后再清理。

公式试算可以用文件，避免终端的 JSON 引号差异：

```json
{"power": 100, "defense": 80, "resistance": 0, "damage_type": "physical"}
```

将上述内容保存为 `inputs.json` 后运行：

```powershell
..\.venv\Scripts\python.exe -m ark_sim preview packages/custom/custom_guard.json --rule rule/my_physical --inputs inputs.json
```

结果为 60。也可用 `--calculation damage.mitigation` 按规则绑定试算，并以 `--scope` 提供局部规则 JSON。`--package` 可重复指定额外包；`--scenario` 选择包内的具体场景。`--override damage.mitigation=rule/my_physical` 在场景作用域显式覆盖一个计算。`--ticks` 使用整数逻辑时间；`--seconds` 和额外指令的 `at_seconds` 通过所选 `time.quantize` 换算。

## 内容包与引用

内容包使用 `schemaVersion: 2`，可包含 `manifest`、`entities`、`abilities`、`buffs`、`selectors`、`behaviors`、`policies`、`rules`、`rulesets`、`scenarios` 或通用 `definitions`。单场景可以写在 `scenarioDraft` 中。

ID 必须是带命名空间的字符串，例如 `unit/my_guard`，没有官方干员白名单。字段名严格检查；描述性资料放入 `metadata`，算法参数放入 `parameters`。导入时重复定义同一 ID 会报冲突。需要复用时创建新 ID，以 `extends` 指定父定义；对象递归覆盖，数组整体替换。可用 `{"$delete": true}` 删除继承字段。

```json
{
  "id": "unit/my_guard_variant",
  "kind": "entity",
  "extends": "unit/my_guard",
  "components": {"attributes": {"base": {"atk": 180}}}
}
```

内容定义 ID 与运行实例身份分开。初始实体使用 `definition` 和 `instanceAlias`；技能命令的 `source` 引用实例别名。同一单位定义可实例化多次。部署命令使用 `entity` 或 `definition`，以 `alias` 命名创建的实例。

```json
{
  "id": "scenario/my_scene",
  "ruleset": "ruleset/ark_standard",
  "initialEntities": [
    {"definition": "unit/my_guard", "instanceAlias": "actor/guard", "position": {"row": 2, "col": 2}, "facing": "right"}
  ],
  "commands": [
    {"at_seconds": 0, "action": "activate_ability", "source": "actor/guard", "ability": "ability/my_burst"}
  ]
}
```

场景、编队 `roster`、绝对出生波次、初始实体和命令中的内容引用决定加载闭包。规则与提供器也进入闭包和版本锁。`dependencies` 声明额外必需定义；`dynamicReferences` 可以声明允许的 ID 集合，但当前运行时不执行动态引用解析。`metadata`、普通参数、表达式输入和事件载荷不会因恰巧含有 `rule` 等字段而被误当成引用。

场景命令和波次的 `at` 是绝对整数逻辑时间，能力时间线的 `at` 是相对施放起点的整数逻辑时间；均要求非负整数，并与 `at_seconds` 互斥。`at_seconds` 使用非负秒数。标准量化公式先按规则参数 `ratio_digits=12` 对秒数与 quantum 的比值舍入，再取上界，避免浮点表达把 6 个单位误算为 7 个；精度参数和整条 `time.quantize` 规则都能替换。

绝对波次一条只创建一个实例；需要多次出生时写多条明确时间的波次。当前不执行 `count != 1` 或非零 `interval_seconds`，编译时拒绝这些配置。路线使用内联 `route`，未实现的 `route_id` 解析会明确报错。

## 单位、属性与资源

单位由 `components` 组成。当前支持属性、资源、能力、部署、空间、行为、生命周期和 Buff 容器。属性名、资源名均由作者指定。`hp`、`sp`、`dp` 和数值角色只在明日方舟预设中声明。

初始 Buff 写作 `"buffs": {"initial": ["buff/my_boost"]}`，也可使用互斥别名 `buff_container`，两个组件不能同时出现。初始列表仅支持 Buff ID 字符串；引用必须存在且种类为 Buff。创建实例时以该实例为来源施加这些 Buff，初始修饰器会参与有效属性计算。

```json
{
  "attributes": {"base": {"atk": 100, "max_hp": 1200, "attack_interval": 1}},
  "resources": {
    "hp": {"initial": 1200, "capacity_attribute": "max_hp", "role": "health"},
    "energy": {"initial": 20, "capacity": 40, "recovery_rate": 2}
  },
  "abilities": ["ability/my_basic", "ability/my_burst"],
  "lifecycle": {"policy": "policy/ark_lifecycle"}
}
```

资源容量和边界由 `resource.capacity` 与 `resource.bounds` 执行，可通过 `capacity_rule`、`bounds_rule` 或资源的 `rules` 更换。资源没有隐含的“初始值就是上限”算法。不同单位和资源可采用不同容量、保留或拒绝策略。

连续恢复是默认驱动。周期恢复显式声明：

```json
{
  "initial": 0,
  "capacity": 40,
  "recovery_rate": 2,
  "recovery": {"mode": "periodic", "interval_seconds": 1},
  "parameters": {"pause_at_full": false, "freeze_while_cast": true, "freeze_cast_modes": ["manual"]}
}
```

周期按整数逻辑时间累计，达到间隔才调用恢复公式；冻结保留未完成周期。`recovery_rate` 表示每秒速率，默认公式读取 `inputs.parameters.rate`。自定义恢复规则可以计算降温、负向变化或依赖属性的变化。满值时继续执行规则；只有显式 `pause_at_full: true` 才暂停计时。明日方舟 SP 包声明只冻结 `manual`，普攻不会停掉自动回复。

事件驱动资源使用显式规则，避免把按攻击/受击恢复误当成时间恢复：

```json
{
  "initial": 0,
  "capacity": 24,
  "recovery_rule": "rule/my_event_gain",
  "recovery": {"mode": "event", "event": "attack.accepted", "owner_role": "source", "amount": 1},
  "parameters": {"freeze_while_cast": true, "freeze_cast_modes": ["manual"]}
}
```

规则 contract 为 resource.recovery，可使用表达式 `inputs.current + inputs.parameters.amount`，也可自定义降温或属性相关算法。
owner_role 支持 source、target、any；driver.condition 使用只读 `inputs.event` / `inputs.owner` 条件。
attack.accepted 每个攻击cast一次，damage.accepted 每次被接受的目标命中，combat.kill 携带真实攻击者与死者。
发出事件时采样冻结资格，后续同帧cast finish不改变该次资格；同一资源不得同时用legacy recovery_per_attack与attack.accepted event驱动。

技能可在 `activation.on_start` 声明同步效果数组，例如切换模式资源、应用技能Buff。
它在支付并登记cast后、同tick下一次自动攻击采样前执行，整体失败原子回滚；技能专用的at_cast视图在这些效果后更新。
`activation.parameters.auto_only=true` 会拒绝玩家强制开启，自动系统仍按合法条件启动。

Buff可声明 `control`，例如 `{"move":false,"attack":false,"abilities":false,"block":false,"interrupt":true}`。
各字段均为boolean，可独立省略；多个活动Buff对许可按AND合并，清理一个不会移除另一个限制。
半开到期后许可恢复，interrupt是显式的既有施放取消策略；已发弹道与未发前摇按各自生命周期区分。

成长使用 `growth` 或 `components.attributes.growth`：`{"atk": {"rule": "rule/my_growth", "level": 120, "parameters": {}}}`。`rule` 可省略，此时使用规则集、场景、拥有者、组件或该属性的 `attributes.growth` 绑定；显式 `rule` 则优先选择该实现。编译阶段会确认有可用绑定。规则输入为 `base`、`level` 和 `growth_parameters`，等级不受官方精英阶段限制。单属性规则可写在 `attribute_rules`，例如 `{"atk": {"attributes.effective": "rule/my_effective"}}`。

## 技能、Buff 与状态图

技能使用 `activation`、资源成本、可选 `selector` 和有序 `timeline`。激活模式支持 `manual`、`automatic_attack`、`on_deploy`、有明确事件的 `passive`。时间线可有限重复，并能组合伤害、治疗、资源变化、Buff、生成、发事件、直接坐标移动、状态转换和延迟效果。

```json
{
  "id": "ability/my_burst",
  "kind": "ability",
  "activation": {"mode": "manual", "costs": [{"resource": "energy", "amount": 20}]},
  "selector": "selector/my_front_area",
  "target_capture": "each_hit",
  "timeline": [
    {"at_seconds": 0, "effect": {"op": "apply_buff", "target": "source", "buff": "buff/my_attack_boost"}},
    {"at_seconds": 0.2, "repeat": {"count": 3, "interval_seconds": 0.2},
     "effect": {"op": "damage", "target": "selected", "damage_type": "physical",
       "rules": {"damage.base": "rule/my_skill_power", "damage.mitigation": "rule/my_physical"},
       "on_success": [{"op": "modify_resource", "target": "source", "resource": "energy", "delta": 2}]}}
  ]
}
```

完整样例包括对应的选择器、单位与规则。成本、时间线任务和施放状态原子启动；无法支付时不扣除部分资源。`read_mode` 可分别配置来源和目标属性的 `at_cast`、`at_launch`、`at_hit` 读取。被拒绝的伤害走 `on_failure`，不执行命中成功返还。

Buff 支持 refresh、independent、add、extend、max，持续、周期与层数分别由计算接口决定。修饰器使用 `attribute`、`layer`、`value` 与可选 `stacks`；单条修饰器的 `rule`、`operation` 暂不执行，编译时拒绝。替换属性算法应绑定 `attributes.modifier_layer` 或整个 `attributes.effective`。

Buff 和能力的事件订阅采用 `[{"event": "damage.accepted", "condition": "...", "effects": [...]}]`。条件是安全表达式，反应通过事件任务队列执行。Buff 周期采用 `interval_seconds` 与 `effects`。状态图采用 `states: {id: {on_enter: [], on_exit: []}}` 与 `transitions: [{from, to, condition, priority, effects}]`，可用 `condition_rule` 指向 `behavior.threshold`。同一时刻按优先级与定义顺序选择转换。

## 替换公式、整条管线与提供器

表达式读取契约中的 `inputs` 与规则 `parameters` 对应的 `params`，通过独立 AST 解释器执行。支持算术、比较、条件、布尔、字段、索引、列表、字典和受控数学函数；没有 Python `eval`、导入、任意方法调用或状态写入。

计算图节点使用 `expression`、固定 `rule` 或动态 `calculation` 三选一。固定 `rule` 锁定具体实现；`calculation` 保留来源、目标、能力、效果等规则作用域。节点结果是原始值，读作 `nodes.power`。字符串输入是表达式；字符串常量用 `{"literal": "physical"}`。

完整伤害管线返回 `accepted`、`amount`、`allocations` 和 `events`。默认图的属性读取由 `metadata.input_bindings` 声明：例如 `{"attack": {"entity": "source", "attribute_role": "attack"}}`。一个固定伤害管线没有该绑定时可以完全跳过攻击力和减伤读取。护盾等自定义资源可通过结算分配执行。

复杂算法注册独立提供器：

```python
def my_algorithm(inputs, params, context):
    return inputs["base"] * params["factor"]

providers = {"custom.algorithm": {"callable": my_algorithm, "version": "1.0.0"}}
program = Compiler(providers=providers).compile(my_package)
simulation = Engine.create(program, providers=providers)
```

如果内容同时使用明日方舟提供器，需要把所需预设提供器一起注册。提供器签名为 `(inputs, params, context)`，只读上下文可通过 `calculate()` 和 `invoke_provider()` 组合纯计算，没有 World 写入口。提供器可以声明参数 schema。动态子计算可在规则的 `metadata.calculation_dependencies` 声明；聚合提供器以 `parameters.aggregator.provider` 或显式 `provider_dependencies` 声明。

自定义契约可传给 `Compiler(catalog=...)`，编译结果保存类型清单，Engine 与公式试算读取同一清单。编译器检查实际内容需要的计算是否有合法默认或局部绑定；空世界不需要伤害、部署等无关计算。规则集必须声明或继承正的 `quantum`，不会给自定义规则集偷偷补上明日方舟频率。

## Python Builder 与公开运行接口

```python
from ark_sim import Compiler, Engine
from ark_sim.tools.authoring import PackageBuilder, EntityBuilder, AbilityBuilder

skill = (AbilityBuilder("ability/demo")
         .cost("energy", 5)
         .effect(0, {"op": "modify_resource", "target": "source", "resource": "energy", "delta": 2}))
unit = (EntityBuilder("unit/demo", tags=["player"])
        .attributes(atk=10, max_hp=100, attack_interval=1)
        .resource("hp", initial=100, capacity_attribute="max_hp", role="health")
        .resource("energy", initial=10, capacity=20, recovery_rate=1)
        .component("lifecycle", {"policy": "policy/ark_lifecycle"})
        .abilities("ability/demo"))
builder = (PackageBuilder("package/demo")
           .add(unit).add(skill)
           .scenario("scenario/demo", ruleset="ruleset/ark_standard",
                     initialEntities=[{"definition": "unit/demo", "instanceAlias": "actor/demo"}],
                     commands=[{"at_seconds": 0, "action": "activate_ability", "source": "actor/demo", "ability": "ability/demo"}]))
program = builder.compile()  # 与 Compiler().compile(builder.build()) 相同
simulation = Engine.create(program, seed=123)
simulation.advance(30)
snapshot = simulation.snapshot()
record = simulation.export_replay()
```

`Builder.build()` 生成普通 JSON 数据，`write()` 保存内容包。JSON、Builder、路径和目录共享同一个编译流程。`SimulationProgram` 递归只读；每场运行独立保存资源、Buff、施放、状态机、计时和随机流。检查点与回放锁定程序、规则、提供器、数值、随机算法和实现身份；修改实现后应重新编译并重新生成验证证据。

## 当前明确的边界

- 动态引用只支持依赖声明，执行解析尚未支持。
- 装备、天赋、完整养成流程、嵌套状态子图尚未实现；已知未实现字段不会静默通过。
- 自定义 Buff 叠层 policy、中断后退款或继续执行、基于力与重量的 `displace` 尚未支持。直接坐标的 `move` 已支持。
- 单条修饰器的 `rule` 和 `operation` 不支持；层公式和整体属性管线可以替换。
- 数值后端为 `float`/`float64`，可配置量化、精度和舍入；其他后端与 `declarative_graph` 实现明确报错。
- 战斗中的规则热切换未实现；编辑内容默认在下一场重新编译后生效。
- 0-1 导入与合成样例属于模型验证。真实客户端命中帧、移动与教程时序等仍需外部对照，不能把确定回放等同于全游戏准确模拟。

遇到新机制时，先检查能否由现有规则、图和效果组成。需要新底层能力时，增加明确的领域适配器、输入输出契约与独立预期，再把它开放给所有内容包。
## 连续光环与动态目标上限

Buff 可声明 `aura: {"selector": "selector/my_range", "buff": "buff/my_member"}`。
将该 Buff 应用于中心实体时立即建立成员；阶段0在命令和波次任务前清理到期Buff并重算范围，
移动后及新实体创建完成后也立即更新成员，
中心或来源死亡、撤退，以及父 Buff 的半开到期边界均清理成员。
子 Buff 必须无 `duration_seconds` / `duration_rule`、不再包含 aura，且使用
`stacking.mode="independent"`。每个父实例持有各自的子实例 ID，因此重叠施法者
能够独立移除；成员关系保存在 World 中并参与事务、检查点与回放。
直接启动能力也先清理过期Buff，因此到期同tick的at_cast快照不能采到旧增益；
到期前已经捕获的历史快照仍保留当时属性。
最高值覆盖等叠加策略仍由自定义属性规则定义，默认独立实例不代表方舟的最高值语义。

Selector 可用 `limit_attribute: "max_targets"` 读取来源的有效属性，
与 `limit` 互斥。结果必须是非负整数；外部 Buff 或自定义属性公式可修改该上限。
选敌排序和筛选仍由 selector/provider/targeting rules 控制。

效果 `op="regenerate"` 使用可替换的 `healing.base` 数值合同并产生
`regeneration.accepted`，不产生 `healing.accepted`。它适合生命回复而非治疗动作，
保留有效属性采样、资源边界和实际回复量，避免误触发治疗事件订阅。

默认伤害类型是 `physical`、`arts`、`true`；其他名称在编译时拒绝，默认 Ark
伤害管线也在运行时拒绝未知类型。扩展伤害种类时，同时在 Compiler 的
`capabilities.damage_types` 显式声明类型并绑定实际支持该类型的自定义管线，
避免拼写错误静默变为物理伤害。

## 随机、伤害钩子与场景控制

`random` 效果必须声明 `stream`，可给 `probability` 及 `on_success` / `on_failure`。
Kernel sampler 消费一次样本，分支调用纯 `random.check`；子效果可在 parameters.random_sample
读取该样本。失败事务恢复随机消费及全部状态。随机选择器声明 ordering=random 和 parameters.random_stream，
按选中槽位无放回抽样，空集合不消耗随机数。

Buff.damage_hooks 支持 before（source）及 after（receiver）阶段，分别使用 damage.request 与 damage.pipeline。
hook 可声明 rule、condition、samples、group、priority。同一组只执行符合条件的最高优先级成员；
输入包含当前 active Buff IDs。追加伤害保留作者声明的 damage_hook_locks，并追加来源锁，避免递归暴击。
分配目标的 alias/source/target/runtime ID 在接收方钩子前统一解析，最终按实体与资源合并一次提交。
`ark.damage.settlement_scale` 只缩放接收方生命分配，保留护盾次数、其他资源和其他接收方。

`modify_resource.amount_rule` 调用 resource.recovery，其结果是新的资源值；与 value/delta/amount 互斥。
respect_recovery_freeze 按实际正负增量处理。Buff 事件反应使用 emission 时捕获的冻结状态，
同tick施放结束不能让先前被冻结的回能穿透。if_resource_present 可显式跳过无该资源的设备。

部署卡式 spawn（position_from_payload=true）与普通 deploy 共用地形、占位、容量、实例数和冷却规则。
deployable.capacity=0 可不占用部署名额；owner scoped history 防止不同主人共用卡片计时。
免费生成的 paid_cost 默认0。作者以 spawn.parameters.deployment_payment_amount 认领当前cast实际支付
的 battle 部署资源；金额不能超过未分配余额，多次spawn不能复制同一笔付款。
这不自动补齐某游戏特有的卡片回补、锁卡、费用倍率或退场策略，须由内容作者明确转换。

生命资源 parameters.healing_allowed=false 排除普通治疗候选并拒绝普通治疗包；
regenerate 仍可执行。需要明确允许治疗时，在能力或效果 parameters.ignore_heal_immunity=true 声明。

场景 scheduledEffects 列表接受 at/at_seconds、effect 与 metadata；任务在phase0、场景commands之前调度，
使用 system/battle 作为来源。input_lock 效果以 parameters.key/enabled 维护命名输入锁，
有任何锁时拒绝玩家命令；状态、事件、任务均参与检查点与回放。
这些接口可描述剧情/提示与无界面确认策略，UI实际等待时间和客户端暂停时序应另行校准。

## 召唤、范围弹道、位移与时间曲线

M8场景可使用 `timeline` 替代flat `waves`，两者互斥。policy明确选择managed_clear/time_only，
negative_timeout_policy明确选择wait_for_clear/skip_wait。每wave有pre/post delay、max_wait_seconds与fragments，
每fragment有pre_delay_seconds与相对actions；action.kind为spawn/effects，可声明delay/count/interval及托管阻塞flags。
同步effects不能伪持有异步UI成员；未知flags与混用绝对at严格拒绝。
wave/fragment/action起点和托管成员保存在World，death/exit/withdraw均释放实际成员；
晚phase推进按下一tick phase0执行。终局取消自有未来任务，不把取消计作出生完成。

路线checkpoint 1是到达后等待秒数；2是play time；3/4分别是捕获的fragment/wave origin加time。
实例 `parameters.timing_origins` 或spatial.timing_origins用非负逻辑tick声明；timeline出生自动注入实际origins。
缺起点时编译拒绝，不能退回到达后sleep。`movement.wait_deadline`是可替换计算，
默认图委托time.quantize得到offset，保留作者的量化选择。WAIT记录中的position不是额外移动点。
详见 [M8调度](campaign/M8_TIMELINE.md)，原生-1和managed gating正文未恢复，策略属于明示模型。

M8内部日志共享不可变子树，事件JSON值、cause、数值操作数与snapshot格式继续保留。
可变输入脱离，循环和非JSON仍拒绝；不通过丢弃trace字段降低内存。
长程检查点/回放验证按顺序释放各分支，避免重复保留全事件历史。

M7新增资源 `capacity_change_rule`，契约为 `resource.capacity_change`，输入包含current、old_capacity、
new_capacity、parameters与reason。已有bounds继续执行最终夹界。默认Ark策略可在资源parameters中声明
`capacity_change_mode` 为preserve_absolute、preserve_ratio、preserve_missing、fill或birth_full；
birth_full只在实体初始化时补满，之后保留绝对值。最小自定义ruleset没有新绑定时继续使用已有bounds，
显式新模式则必须提供绑定。容量变化产生独立事件，不能作为治疗或伤害计入。

wave可声明 `placement:{rule,stream,sample_axes,sample_zero_range,random_range,offset}`。
position是anchor；sample_axes按声明顺序包含row和col各一次，零范围是否取样必须明确。
Kernel采样后调用纯 `spawn.position`，计算与实际创建同事务。`ark.spawn.uniform_rect` 是明示半幅矩形模型，
parameters.axis_signs控制坐标方向，不被宣称为客户端随机算法。源边框负小数只要仍属合法cell即可，
不强行夹成portal格。

路径规则可使用 `ark.spatial.route` 的parameters.use_route_diagonal与corner_cut；
八邻居模型按距离加权，不允许切角时要求两个相邻正交格都可通过。飞行与WAIT checkpoint继续保留。
spatial.steering可指定 `rule` 与parameters，调用 `movement.steering`，输入为origin/destination、
velocity、speed、delta_seconds与parameters，输出position/velocity。默认库提供可替换的有界速度响应模型；
arrival_radius是模型捕获策略，必须检查运动方向与实际步段，不能无力向侧面瞬移。
velocity保存在World并参与检查点；停止、阻挡和WAIT清除模型速度。

`Engine.create(program)`采用场景seed；显式seed=0也会覆盖场景值。
所有新增数值策略见 [M7进展](campaign/M7_PROGRESS.md)，原生时钟、随机与碰撞对照仍独立记录。

`Buff.on_remove` 是同步原子效果列表。可用 `modify_resource` 的 `value` 字段赋值，
与 `delta` / `amount` 互斥，例如 `{ "op":"modify_resource", "target":"source", "resource":"mode", "value":0 }`。
到期同tick命令之前完成移除效果，历史属性快照仍保持其 `sampled_at` 时钟。

`activation.costs` 支持 `owner:"source"`（缺省）、`"battle"` 或 `"owner"`，最后一个表示
当前实体的ownership.owner。所有持有者先规划、再与on_start效果一起提交，自动就绪检查使用同样的持有者。
例如 `{"owner":"battle","resource":"dp","amount":5}` 支付战斗DP。

`spawn` 可指定 `owner:"source"` / `"target"`、`lifetime_seconds`，并以
`parameters.max_owned`、`on_owner_retire:"remove"` / `"retain"` 管理容量和退场。
部署卡式能力设置 `parameters.position_from_payload:true` 时，命令必须传
`payload:{"position":{"row":3,"col":4},"facing":"left"}`，缺少或非法输入原子拒绝。
选择器 `filters:[{"owner":"source"}]` 只选择自己的存活成员，
`region:{"type":"manhattan","radius":4}` 支持曼哈顿范围。
效果 `trigger_ability` 用 `ability` 引用及可选selector启动选中成员的自动能力。

`area` 效果有 `center:"target"` / `"source"`、`radius`、`filters` 和嵌套 `effects`。
带弹道的能力对主目标发包后，在落地时以当前impact目标位置选择范围成员；
`parameters.wait_for_projectiles:true` 保持施放到实际根弹道全部结束，嵌套schedule不重复算完成。
生命回复等显式 `modify_resource` 可用 `parameters.respect_recovery_freeze:true` 尊重施放冻结。

`push` 的 `force`、`direction` 与参数通过 `movement.displacement` 取得 `{distance,duration}`，
再以可替换 `movement.distance` 规则逐tick执行。零计划合法，墙体和地图边界按点体网格模型裁剪实际路程。
必须显式绑定推力模型，标准底座没有冒充客户端物理曲线的默认值。
`Buff.movement_damage:{"effect":{...damage...}}` 配合正interval_seconds采样实际距离，
向自定义damage.pipeline提供 `effect.distance`。刷新/延长/移除/到期前flush，cursor参与事务和回放。

`recovery.selector` 可要求有效成员；`empty_value`、`selector_interval_seconds`、
`interrupt_when_empty` 配置缺少成员时的资源行为。
纯提供器 `ark.attributes.time_layers` 可替换attributes.effective：modifier.parameters.time_curve
支持 `type:"linear_remaining"`（使用所依附Buff的时间范围）或
`type:"staircase", step_seconds, max_steps`。它按属性捕获时钟求值，延迟命中不会重算at_cast快照。
## 新增资源与路线接口

当前底座已经支持按能力精确冻结资源：资源spec可声明 `recovery_freeze_abilities` 的exact能力ID列表，
它与既有 `parameters.freeze_while_cast/freeze_cast_modes` 按OR组合。列表允许为空；能力必须由对应actor拥有。
所选技能和普通攻击采用相同activation mode时，可以用该名单区分，避免把所有普攻一并冻结。

显式 `recovery_freeze_rule` 绑定纯Bool `resource.recovery_freeze`，规则必须声明
`metadata.recovery_freeze_authority="final_override"`，输出作为最终决定；默认路径不新增隐式绑定。
该接口可替换冻结算法，仍受规则类型、原子回滚、emit快照与回放身份约束。

资源 `recovery.selector` 的门关闭中断可用 `interrupt_abilities`、`interrupt_cast_modes` 精确限定，
同时提供时为交集；无名单保留旧中断全部cast语义。缺selector、错能力种类/所有权/模式在编译期拒绝。
说明与独立例子见 [资源接口](campaign/candidates/M10_CAST_RESOURCE.md)。

原生路线消失/出现需显式 `transition_policy`；非零reachOffset需显式 `reach_offset_policy`。
这两个策略分别调用可替换的 `movement.transition`、`movement.checkpoint_position`，
隐藏、已发射效果、光环与重现位置/距离账本的行为由声明模型解释，不能只填原生枚举后静默直走。
目前随机checkpoint offset和非零reachDistance仍要求额外模型，编译会拒绝未支持输入。
可运行例子与边界见 [路线接口](campaign/candidates/M9_ROUTE_REVIEW.md)。

历史第6章联合底座的计算契约总数为98，当前106项底座及新增接口见 [逐格地图与技能时钟](campaign/CHAPTER09_CHANNEL_MAP.md)。以下M10首章综合内容保留历史身份，位于 `packages/campaign/mainline_models/level_main_00-10.m10.json`
和 `level_main_00-11.m10.json`，模型与客户端待对齐项保留；不要把partial场景的获胜解释为原生完整干员已实现。

## 部署、显隐与地块接口

M68新增 `targeting.availability`、`selector.eligibility`、`targeting.eligibility`、`area.members`、`passive.toggle`、`tile.contact`、`terrain.tile_options`、`blocking.obstacle`、`behavior.decision` 与 `deploy.connectivity`。
部署的 `deployable.cooldown_start` 可选 `deploy` 或 `retire`；连通性使用显式原路线起止列表，拒绝封死任一受保护路线。
完整字段、公开命令及可替换提供器示例见 [M68部署与连通性](campaign/M68_DEPLOYMENT_CONNECTIVITY.md)。
当前主底座已包含经回归的复活、状态免疫、周期环境伤害、磁盘事件存储和分支／机关／定向弹道能力。各关所需内容消费者和全程证据仍独立验收；最新底座身份见 [当前状态](campaign/CURRENT_STATUS.md)。

## 自定义 Buff 应用计划

主底座支持 `buff_application`，可以用纯表达式、计算图或提供器决定施加哪些 Buff、移除哪些实际实例，以及每次应用的时长。内核不识别寒冷、冻结或干员ID。

效果必须声明有限的 `allowed` Buff ID 列表和 `application_rule`；列表中的全部定义都会进入编译依赖闭包，即使本次规则没有选择其中某项。规则实现 `buff.application`，输入包括source、target、status、现有instances、request、allowed和目标attributes。request就是效果的parameters。

例如，下面的表达式规则把时长放在效果参数中，便于编辑技能：

```json
{
  "id": "rule/custom/atk_up_application",
  "kind": "calculation_rule",
  "contract": "buff.application",
  "implementation": {
    "type": "expression",
    "expression": "{'accepted':True,'operations':[{'kind':'apply','buff':'buff/custom/atk_up','duration_seconds':inputs.request.seconds,'stacks':1}]}"
  }
}
```

技能的on_start或timeline效果可以使用：

```json
{
  "op": "buff_application",
  "target": "self",
  "application_rule": "rule/custom/atk_up_application",
  "allowed": ["buff/custom/atk_up"],
  "parameters": {"seconds": 10}
}
```

其中 `buff/custom/atk_up` 是普通Buff定义，例如添加atk属性的flat层。修改属性层、增幅、时长表达式或应用规则，不需要在内核增加专用分支。

完整可运行例子见 [buff_application_example.json](../packages/custom/buff_application_example.json)。当前主目录CLI验证通过，实际手动技能使ATK从10变为30，300tick到期后恢复10。修改Buff的value、效果的seconds或application表达式即可改变这三个可编辑部分。

计划输出须为精确的 `{accepted,operations}` 记录，accepted是严格Boolean。apply操作限定已声明Buff、有限非负秒数和正整数stacks。remove操作须携带目标当前真实实例ID和generation，不能使用其他单位的句柄；回调刷新实例后旧代数移除会被跳过。

显式持续时间0按半开时段立即到期，不等于永久Buff；该实例不贡献属性、不执行立即效果，也不打断施法。未覆盖且未声明默认时长的永久Buff仍保持永久。整体计划先验证再原子执行，畸形数据不会留下部分费用、Buff或任务。

拒绝或空操作计划是纯no-op，检查点、事件、任务和RNG均不改变。来源或目标在同步回调中退场后，不能继续拿旧计划作用于变化后的实例。

当前联合底座已支持真正已发射载荷的调用链与化身约束、实际范围成员的载荷授权，以及可选lifecycle.exit清算规则。新建回调不能借旧载荷权限，来源／目标复生后的旧计划受到限制；退出计数不伪造战斗死亡。规则字段和当前参考范围见 [退出清算](campaign/CHAPTER06_EXIT_ACCOUNTING.md)。敌人模块、整关和实机核对仍分别验收。

当前主底座也允许Buff在自己的周期／事件效果中使用`remove_buff`移除自身定义：这是移除既有实例，不构成递归构建。`apply_buff`自身、互相构建及显式依赖自环仍拒绝。需要精确移除某个代数实例时继续使用上面的纯申请计划与真实句柄。

静态自定义地块可以在`scenario.map.tile_mechanics`中绑定自己的名称与来源选项，不需要修改内核的地块名称清单。例如：

```json
{
  "custom_fence": {
    "type": "declared_static_tile",
    "expected_options": {
      "buildableType": 1,
      "passableMask": 2,
      "heightType": "LOWLAND"
    },
    "expected_blackboard": null,
    "expected_effects": null
  }
}
```

对应`map.tiles`记录必须包含同名`tileKey`，其buildableType／passableMask／heightType和blackboard／effects的类型及值须与声明精确相同。上例可地面部署、地面路径不可通过；飞行路径继续使用飞行语义。没有profile的未知地块与非空未知黑板／effects均拒绝；动态周期、接触、占据等机制应使用对应可执行profile。名称不决定通行行为。

完整关卡使用内容提供器时，须向`Compiler(providers=...)`、`Engine.create/restore(..., providers=...)`和公开重放传递同一注册表。提供器文件、版本及计算体参与身份；现有全程执行工具支持显式提供器与可持久化公开对话驱动，入口见 [当前交付契约](campaign/REFERENCE_FIRST_ACCEPTANCE.md)。

纯Buff申请计划的`duration_seconds: null`表示明确申请永久实例。它只接受定义未固定时长、未声明duration_rule、且当前完整规则作用域实际算出`buff.duration=0`的Buff；自定义时长算出有限值时准确拒绝。整个计划先验证，操作前再核，回调令后续时长改变时完整回滚。正常有限时长与显式0仍分别保持原语义。

Buff的每次周期回调现在是一个完整事务，包括全部效果、同步回调和重新排程。后续效果失败时，前面同周期的资源、事件、随机数和已产生任务都回滚；已经由调度器出队的失败触发任务不会伪装为尚未执行的空闲边界。

显式`no_source_damage`请求可用于真正owned Buff定时器。它接受`attack_type`为`NONE`或`BUFF`、严格Boolean的`damage_without_modify`及其他标记。True直接使用固定请求金额，跳过伤害修正与目标伤害hook，继续尊重资源边界、实际扣血、生命周期和`ignore_for_sp`；False保留原计算与hook路径。伤害事件source为null，origin保存声明来源和实际Buff timer的owner／instance／generation，不能借actor施法或弹道权限。

地块纯查询还提供`occupant_selection_states`和去重排序的`occupied_side_unit_type_bits`。例如`[params.side, params.type_bit] not in inputs.occupied_side_unit_type_bits`可以按侧别与类型位排除占位者；复合掩码会拆成实际位，不以部署能力代替角色分类。查询不修改世界、事件、任务或RNG。

以来源为中心、每次施放只执行一次的范围效果应显式写`"target": "source"`或`"target": "self"`。默认selected语义会对每个选中目标各执行一份效果，适用于逐目标中心的范围技能；不要让多个施法资格目标意外重复派发同一来源范围伤害。

当前底座还支持与选中编队分列的`scenario.cards`：唯一有限实体ID列表、显式库存资源和部署约束均需声明，
进入正常依赖闭包，卡片公有部署不会改变`scenario.roster`。自定义`area.members`提供器可通过
效果`selection_projection: {"defaults": <完整类型化默认状态>}`取得当前来源与候选对象的Buff／运动状态。
公开`set_motion_mode`在同一事务中同步物理WALK0／FLY1与资格地面位1／飞行位2。
完整字段、严格校验和可替换规则说明见[卡片与范围接口](campaign/SCENARIO_CARDS_AND_AREA_PROJECTION.md)。

当前9ad主底座支持显式`restart_behavior`效果：

```json
{
  "op": "restart_behavior",
  "target": "self",
  "state": "phase_two",
  "parameters": {
    "abilities": ["ability/custom/normal", "ability/custom/skill"],
    "reset_attack_clock": true,
    "initial_cooldowns": {"ability/custom/skill": 7},
    "reason": "enter_phase_two"
  }
}
```

能力列表须唯一、有限且由实际目标拥有，state必须存在于目标状态图，冷却秒数须有限非负，reset选项为严格bool。取消声明cast、状态退出／进入回调与时钟建立在同一事务中；回调使目标退场时停止后续写入，异常完整回滚。已发射弹道继续遵守原声明生命周期，未列cast不被取消。没有该效果的普通transition保持默认行为。纯目标资格和可用性规则可读当前逻辑time／seconds／quantum；提供器仍不能修改World或RNG。来源和独立边界见 [状态机重启](campaign/BEHAVIOR_RESTART_DESIGN.md)。

逐格地图场域与拥有能力的冷却／中断已经进入生产底座。内容字段、局部数值规则和精确依赖校验见 [逐格地图与技能时钟](campaign/CHAPTER09_CHANNEL_MAP.md)。
