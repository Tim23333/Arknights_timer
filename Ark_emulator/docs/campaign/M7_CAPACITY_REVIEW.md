# M7 通用容量变化独立审阅

2026-10-02，新增 `tests_v2/test_m7_capacity_review.py`，只使用真实Compiler/Engine与数据规则，未修改生产源码、M6内容或旧期望。当前短测试 **12 passed in 1.36s**。这是通用模型合同审阅，不是能天使native当前HP公式或完整干员审批。

## 审阅合同

通用接口为 `resource.capacity_change`、每资源 `capacity_change_rule` 和 `parameters.capacity_change_mode`，输入current/old_capacity/new_capacity/reason及initializing。资源bounds负责夹界，Buff.apply/remove捕获并同步有效容量，动态capacity由tick检查，Lifecycle标识出生初始化。

独立模型基准为HP500、基础capacity1000，动态max_hp属性提升50%到1500，真实health生命周期开启。

| 策略 | apply后HP | remove后HP | 证据 |
|---|---:|---:|---|
| preserve_absolute | 500 | 500 | 实际断言通过 |
| preserve_ratio | 750 | 500 | 实际断言通过 |
| preserve_missing | 1000 | 500 | 实际断言通过 |
| fill | 1500 | 1000 | 实际断言通过 |

这些变更未发 `healing.accepted`，不能把容量同步当治疗来触发返SP。原生公式是否对应某一项仍pending。

## 实际边界与反例

1. Buff expiry：base1000/1000，在增益下真实调整HP1400，到1秒半开expiry后立即1000/1000；下一包true1实际999，`damage.accepted.amount=1`，没有把此前超容量部分混进伤害统计。
2. birth_full：initial buff在initializing阶段将满血出生提升到1500；移除后将HP受伤至400，再次运行中apply不会偷偷补满，保持400。显式选用birth_full的语义与普通伤残场景输入是独立内容策略。
3. live aura：源radius1范围给成员永久independent maxHP层，ratio模式初始500→750；移动离开立即去掉此来源层并回500/1000，没有等下一tick才清。
4. 自定义rule：声明current+17实际得到517。另真实runtime除零规则在apply阶段失败，全checkpoint保持，包括Buff、容量记录、HP、任务、事件；remove阶段失败也完整恢复已施加的Buff与此前状态。
5. 生命终止：自定义capacity policy返回0后，HP0、aliveFalse、state dead，不能只夹到0而留下存活actor。
6. 动态capacity：直接改变容量属性1000→2000，ratio模式400→800；再2000→500，HP800→200，说明使用正确observed old capacity，而不是新值作为分母。
7. 检查点与回放：用真实技能命令施加1秒Buff，半途保存并跨expiry执行，恢复与输入回放snapshot精确一致。

## 当前结论与身份边界

当前12例scope内没有新增阻断。未选择或批准角色专属nativeHP公式；默认absolute夹界是模型合同，ratio/missing/fill/birth_full是显式可替换策略。仍需在root定型源码下重新执行全套检查和模型基线，短测试期间生产身份变化的结果不得升级为最终身份通过。

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m7_capacity_review.py -q
```

全部失败预期均保留严格状态/实际伤害条件；没有mock资源、空handler或V1执行证明。同期新 `roster.profiles.json` 封存当前容量行为witness与历史超容量漏洞，详见 `M7_ROSTER_GAPS.md`，M6文件保持冻结。

## 静态容量轮询优化追加独立复核

追加真实规则/provider场景检验优化，不断言私有cache实现：

- 自定义 `attributes.effective` provider读取context.time，未声明static依赖时每tick容量1000→1100→1200→1300，ratio HP500→550→600→650，并在中间checkpoint恢复与输入回放精确一致。
- 同一个provider仅改变 `attribute_time_dependency` descriptor会改变锁定program fingerprint；优化权限是显式且被身份封存的合同，不能因metadata改变而复用旧证明。
- 容量表达式使用动态输入索引 `inputs[params.key][params.field]` 时保守轮询，直接ctx.set属性后HP随容量同步；graph里读取context.time也不能被当纯参数跳过。
- 运行时resource.capacity规则覆盖由静态参数规则切至属性规则，下一tick识别真实容量2000/ratioHP1000。
- 失败事务包含base属性、resource spec及容量签名变动，完整checkpoint回滚；恢复一个含尚未同步的base变动的检查点，下一tick仍正确同步，不能因签名cache恢复而丢更新。

发现两项实际遗漏，均已发root，独立预期没有放宽：

1. `ctx`合法别名：`inputs.capacity_parameters.capacity + ctx.time*100` 被AST当成静态；advance3后observed容量仍1000/HP500，期望1200/HP600。完全等价的context写法通过。检查表达式环境中的全部合法context根，而非只识别单个名字。
2. `attributes.layers`：已有max_hp direct_ratio+.5，但初始只启用flat；ctx.set启用direct_ratio后，实际容量应1500/HP750，签名遗漏layer顺序使其仍1000/HP500。有效layer顺序属于容量依赖，即使base/modifiers/rules/spec本身未变。

顶层provider声明还发现两条跨调用遗漏：内置 `ark.attributes.layers` 可以调用被owner覆盖的 `attributes.modifier_layer` 规则，也能通过parameters指定自定义aggregator provider。两条下游计算分别实际读取context.time；顶层仍带modifier-only描述，却不能据此跳过轮询。独立场景含flat0 modifier以真实进入该层，advance3都要求容量1200/HP600，修前都留1000/500。静态判定需确认实际delegate和aggregator仍满足已审查依赖，无法证明的自定义下游保守轮询。

修复与最终同身份验证结果在core冻结后追加；优化不得静默将动态数值固定为旧容量。上述新场景使用真实Compiler、Engine和有数值行为的自定义pure provider，不使用stub域系统。

### 最终冻结验证

root修复以上四项遗漏，独立预期未改。最终fresh **23 passed in 2.01s**；此完整运行包括普通ratio expiry的command replay与checkpoint恢复、自定义读time属性provider的恢复/输入回放、以及失败signature事务后恢复仍能识别下一容量变动。无新scope阻断。

实际静态跳过条件已收紧：AST识别context与ctx，签名纳入有效层与属性参数，检查有效 `attributes.modifier_layer` 下游绑定及aggregator静态依赖描述；不满足条件的custom provider、graph、动态输入索引及未知下游继续轮询。描述字段进入RuleRuntime/provider身份，不能用改descriptor复用旧回放。

默认规则runtime fingerprint：`ba907a8c5912717b60e9ca3a7f0339541a0f3439694a5b6adc1b8e451104fe95`。自定义provider场景另含该测试provider版本/实现身份；它们的回放在同次fresh运行真实校验。

| 冻结身份 | SHA256 |
|---|---|
| tests_v2/test_m7_capacity_review.py | 091793d9b7f2885c3316cc686468684dfa512796ac21d909529c57c749c6569f |
| ark_sim/domains/resources.py | 1de56249b46f260613187eea093a6ad0d4a3bbd8d978ed9095a59d93985771d3 |
| ark_sim/domains/providers.py | fa7bc92b3e1e2b6b215af552c4259909cda6defa94b22777fc2e637ce58b1de6 |
| ark_sim/presets/providers.py | fa2366b49dba24d15ef0dd81915ed9968fb0e55b1558b00a86529447db271a12 |

生产修复均由root完成，复核者只改本M7测试与文档。M6文件和已冻结source提案未重写；历史失败记录不提升为新身份通过，以上模型合同通过也不批准native角色HP公式或正式主线。

## 全suite兼容修复后的身份

旧全suite暴露最小自定义ruleset未绑定新contract及isolated context新增接口依赖，见新 `M7_RUNTIME_AUDIT.md`。root修复而未改旧tests。按后续派发追加两条独立兼容预期：未声明策略的旧ruleset仍用绝对HP并经既有bounds夹界，下一1点伤害正确记1；显式preserve_ratio却无capacity_change绑定时编译拒绝。

当前fresh完整 **25 passed in 2.09s**，仍含前述custom provider、AST依赖、下游依赖、signature和真实cp/replay预期。新的默认runtime为 `fcfb5a39dd8d020160d2e145f14d34ed3040310f9b23da95ae23833df3fe6910`；测试SHA `6ee242aa50f07eb530b503493bb7f478a3a2448efc48a8dade5258b783910adf`。前面23例及其SHA保留为此前身份，不自动重标为兼容修复后的证明。
