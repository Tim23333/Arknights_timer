# M9 候选路线：可替换空间模型与严格门

候选路径为 `D:/Arknights/Arknights_timer/unpack_work/campaign_m9_candidate/ark_sim`。Primary Ark_emulator/ark_sim绝不修改，保持f8。本批修改候选movement/context/abilities/effects/buffs/providers、spatial_validation/capabilities及两个JSON契约/预设；没有修改root拥有的候选schemas.py/resources.py。Root另有独立scheduler-fork性能修改，双方一起冻结后测试，两个patch分别保留。

这是声明式模型，不是客户端checkpoint或投射/FSM正文恢复。原生旧dump checkpoint枚举确证DISAPPEAR5、APPEAR_AT_POS6；来自第1章真实脚本，不以关卡/敌人ID写入domain。源码方法体为空的限制见CHAPTER01_SOURCE_AUDIT。

## 内容接口

含消失/出现的route必须声明：

```json
"transition_policy": {
  "rule": "rule/m9_living_transition",
  "parameters": {
    "hidden_effects": "reject",
    "hidden_auras": "suspend",
    "launched_source_effects": "retain",
    "resource_timers": "continue"
  }
}
```

纯契约movement.transition输入kind、position、checkpoint与parameters，输出 `{hidden:bool,relocate:bool,position:{row,col}}`。Driver严格检查输出形状、kind语义和实际位置/地面passability。不能通过自定义rule把DISAPPEAR变成visible或APPEAR变成hidden。位置/其它模型参数可由内容规则替换；默认provider是generic living transition，未注册任何隐式绑定，缺policy直接编译拒绝。

非零reachOffset必须声明：

```json
"reach_offset_policy": {
  "rule": "rule/m9_checkpoint_cartesian",
  "parameters": {"axis_signs": {"row": -1, "col": 1}}
}
```

纯契约movement.checkpoint_position输入已经转为V2坐标的base position、原始x/y offset、parameters，输出真实目标位置。默认公式row=base.row+sign.row×offset.y，col=base.col+sign.col×offset.x。native x→col/y→row翻轴时幅度保留，y翻号显式由sign.row控制；不是把base row再翻一次。axis_signs只能整数±1，不能用bool。其它纯公式可以替换，运行期同样检查cell bounds与ground passability。

实际MOVE/BFS或FLY直线路径使用该结果，未将非零offset归到tile center。边框采用既有cell语义floor(coord+.5)，允许格内负偏移，拒绝出地图和墙中目标。未知randomizeReachOffset、非零reachDistance仍严格拒绝；本模型不猜这些算法。

## 世界状态与隐藏策略

只有实际执行transition才写 `spatial.route_hidden`。未使用机制的actor不会新增hidden=false字段，不产生visibility event；零offset不调用新公式。消失保持runtime.alive、HP、wave成员与未清场状态，只清理当前阻挡/速度/旧路径并取消未launch casts。不会调用Lifecycle.retire，不会虚增kills/leaks，不触发managed-clear释放。

隐藏期间只推进WAIT/APPEAR，不能隐形MOVE；资源恢复、CD、Buff到期与next_attack绝对时间继续。当前只支持resource_timers=continue，pause会严格拒绝；cancel cast不重置其已经写入的CD/next_attack。隐藏timer可以继续到appear，出现后普通移动仍受controls/behavior/阻挡限制。

默认 `hidden_effects=reject`：默认selector排除hidden；captured targets与scheduled/direct damage、heal、regenerate、apply_buff、area-center、push/move也检查当前visibility；HP modify_resource与damage allocations不能绕过。普通非健康资源的modify_resource继续，实际resources.adjust/World手动写入仍是低层授权API，不是“所有资源绝对不可修改”的承诺。

隐形并不等于死亡。已经launch的投射对hidden目标在impact时默认拒绝，即便cast snapshot仍记录其alive；无需重新选敌。隐藏攻击者的已launch投射由 `launched_source_effects=retain|discard` 控制，默认retain；未发出的攻击取消、新Ability.start拒绝且不支付资源。direct持续HP effects默认也拒绝，连续resource恢复由resource_timers选择继续。这些都是模型边界，客户端仍pending。

`hidden_effects=allow` 是另一显式profile，允许已经明确绑定hidden target的效果；默认select/area候选依然不选hidden，因此不是自动重新加入选敌。`hidden_auras=suspend|retain`控制隐藏emitter/source的可见成员贡献：default suspend会移除其派生成员，保留parent Buff/TTL；retain可保留可见成员。隐藏recipient始终不被默认selector选中，因此丢失成员并在appear后同步重新加入。Owned token自身仍可见而owner/source隐藏时，同样检查parent.source，没有漏掉该关系。

出现的relocate直接重置position/path/velocity，重新同步blocking/aura；不调用travel、不累计distance_travelled、不制造movement.traveled。此前真实物理距离ledger仍保留，出现后的真实走路可以继续产生距离伤害。没有用地面位移DoT为地下/portal距离收费。

## 严格编译与回滚

DISAPPEAR/APPEAR必须配对：拒绝nested disappear、orphan appear、未出现就结束以及hidden状态中的MOVE；可有多个WAIT。APPEAR必须有合法坐标，ground不能进入墙；FLY可在墙上出现。偏移必须精确x/y有限数、适用MOVE/APPEAR且有显式policy，随机offset/未知checkpoint/非法轴/地图边界外均拒绝。

capability检查两种rule的真实contract，不仅解析字符串ID；flat、timeline、initial entity的component.spatial.route也经过有效route检查，避免override把错contract留到运行期。新计算仍是纯规则，严格运行期结果检查可回滚坏transition/offset的状态、事件与任务；Session保留failure并fail-stop，没有伪称异常后会话可继续。

## 独立验证

`tools/candidates/test_m9_routes.py` 只在candidate加载后运行；入口runner在sys.path最前注入candidate，并检查所有已载入ark_sim模块路径。Primary tests_v2全套不会收集该文件。

共同冻结后fresh **39 passed，6.88秒**，包括hidden alive+managed+资源、captured/direct/area与重定向allocation、发射前后策略、aura/owned关系、出现无rupture费用、真实offset/规则替换/坏输出回滚、坏policy/配对/轴/地图/墙/unknown enum，以及完整checkpoint/replay一致。

扩展运行root alias/fork新测试及既有M7 spatial、M8 timeline、event resources、owned deployment、abilities、auras、spatial与engine：213通过、1失败。唯一失败为审查runner未把primary工具根加入路径导致 `import tools` 不可见；只修新runner的路径后，该inventory用例单独fresh **1 passed，0.33秒**。两次运行同一candidate core，没有放宽预期或修改冻结源码。该记录不冒称一次214全绿。

初版共同candidate implementation digest为 `39c6047046b27176c6e1adf9c149d503dbfcb34f6a01868164cbc533229e1bc1`。JSON契约/预设的实际SHA另存m9_route_source_hashes.json，因为implementation digest本身只覆盖Python。Primary仍 `f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263`。

M9_ROUTE_VISIBILITY.patch仅包含路线拥有的逻辑改动，剔除root在abilities/buffs的next_task_id读取优化；M9_SCHEDULER_FORK.patch另存。审查diff将双方换行统一成LF以避免JSON全文件换行噪音，source hashes仍锁实际字节，不作换行归一化；baseline原字节保留在base64记录。没有promotion、整关或客户端通过声明，没有审批收据。Root将另做相同300tick primary/candidate state/events/tasks/RNG比较；本报告不提前代替该证据。

## 实际0-1 nullable兼容修订

Root扩大候选回归后，先补齐候选唯一离线0-1 JSON（没有复制或导入V1 Python）。真实import套件6过1失败，唯一CompileError来自原始checkpoint.randomizeReachOffset=null；所有对应reachOffset为x0/y0。初版严格bool检查错误地将未定义null当成随机采样请求。

修订只改变候选spatial_validation的这条门：缺失/None/False视作未定义false，数据本身不改；True继续拒绝未声明的随机sampler，整数0/1以及字符串false均继续拒绝，不使用Python truthiness把0当布尔。新增真实import编译/输入不变/无legacy模块导入断言，及null/False/缺失/True/0/1/字符串差异。原39加8为47；联合真实import7，fresh **54 passed，7.06秒**。

旧39c patch、doc、source hashes、validation、test/runner与旧spatial_validation原始字节先封存 `history/39c6047046b27176/`。修订candidate implementation digest为 `cadd4c8403816b9e0f6e5ab9466be302e170d3940a74f001a6c5774c22c75a57`。旧39c结果不迁移到新身份。

Root旧39c 300tick比较显示World/tasks/RNG/semantic state精确相同且event count21536相同；raw event hash不同，firstdiff为calculation.trace.runtime_fingerprint及resource.changed.target从alias到canonical ID。这里是预期身份/API规范化差异，不能宣称跨版本raw日志相等。本报告引用root告知的比较范围，不替代其独立比较文件。

新 `tools/candidates/verify_m9_nullable_baseline.py` 先注入并核验candidate模块，使用primary固定0-1内容/命令，在此新身份下执行完整胜负、cp300与完整replay，另存m9_nullable_baseline_20261002.json/log/replay。结果必须以该新报告为准，旧39c或primary长程不能被重标。

该新基线实际完成并passed：0-1模型11kill/0leak/victory，pending0；cp300续跑与完整命令replay均与同身份主运行的全部观察值相等，event_count181808。标准/自定义规则集独立damage850/60与其replay也均通过。结果只证明新candidate的模型与确定性，不证明客户端或跨版本raw eventhash相同。
