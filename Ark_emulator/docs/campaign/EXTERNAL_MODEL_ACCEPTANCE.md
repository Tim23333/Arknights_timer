# 外部模型合同与不可变战斗证据

## 分层

`campaign_model_acceptance.py`把转换要求与审查资料放在独立sidecar，战斗包保持原始字节。
`case_identity`同时锁内容、commands、contract、固定roster、native source和实现digest；改变合同也会使外部receipt失效，
但审核资料不进入战斗program/runtime fingerprint。算法、单位、地图、波次或操作变化仍必须产生新的战斗输入与实际验证。
旧`campaign_progress.py`及metadata草案保留原样，当前M12源码没有因此修改。

0-10第一份external draft路径：

- `packages/mainline/v2/main_00-10.json`：原0fb内容的精确字节副本。
- `scenarios/mainline/v2/main_00-10/commands.json`：原12条固定命令的精确副本。
- `packages/mainline/contracts/main_00-10.json`：来源、必需机制、已执行引用、client_pending与真实model gaps。
- `validation/campaign/external_first_model_draft_20261002.json`：结构/身份/引用验证，不是批准。

## 门槛

1. 实际编译的原生level、12人roster/config、选技native ID及owned引用必须匹配；SPAWN按definition人口必须匹配原生case。
2. 每个required机制必须绑定经审阅的实际证据。独立case检查selected case、core/package/test源码、实际事件、CP/replay。
3. full-suite节点检查实际测试模块/函数、锁定helper及有限literal CASES/parametrize集合、执行artifact和真实shell launch环境。
   AST检查只读取常量字典、有限常量comprehension及显式追加键，不执行helper代码；不把`pytest -q`说成逐node事件导出。
4. 完整stage检查内容/commands及program/runtime身份、胜利/零漏怪、出生与kill守恒、所有记录commands合法、完整snapshot/event观察及CP/replay。
5. 外部receipt必须有独立reviewer、五类语义checks、原始source review与实际测试来源，并绑定完整case identity。
   包或sidecar的自述标志不能取代外部receipt；有pending model gap就拒绝。

`completed_stage_gate`核对同输入已经完成的三路运行；它不修改旧报告，新增外部结果继续保留原report SHA。
该接口避免仅添加审核metadata而制造新的战斗版本，也不允许把改过的战斗数据、旧core、短前缀或单次胜利当新整关通过。

## 当前实际结果与新发现

原M12 0-10完整flat模型已35kill/0leak，CP/replay全部通过。因此100个合同要求的现有引用可解析。
独立语义复核仍发现源`managedByScheduler`、`dontBlockWave`、`maxTimeWaitingForNextWave`没有由flat绝对时刻消费。
该发现作为真实model gap保留，合同仍拒绝批准；不能把有数据但没有消费者的问题仅改名为client_pending。
M14新内容将使用已有Timeline管理成员、波次门和明确负等待数学策略，真正语义变化需要重新执行关卡。

61项初扩展加1项known-gap拒绝门，共62项最终通过，日志`external_contract_known_flow_gap_tests_20261002.log`。
覆盖错level/source/content/roster/选技/owner/config、假节点/参数/helper、缺外部审阅、旧合同、旧FP、非法或缺命令、
人口/kill守恒错误、prefix、缺完整CP/replay及已知源消费缺口。首轮“wrong skill”夹具误用了同一个桃金娘技能，
失败保留后改为另一实际队员的技能；未改实现迁就测试。

原始source字段另由root不调用builder验值逻辑直接读取：2526个JSON pointer、270个Unity对象字段、68实际源锁及历史recipe SHA一致。
这证明原始值与身份，不自动证明每个字段的语义消费者。真实primary-suite launch及配对终局tool记录另存
`m12_primary_launch_provenance_20261002.json`，只抽本任务相关调用；source-at-completion记录没有被改写成source-start guard。

正式36关计数在本模块中尚未提升。之后的每关有单独native消费审阅及整关证据；共享干员模块需显式同定义/规则/provider/fixture作用域证明，
源报告input SHA和运行身份保持原值。未知适用性不得通过删除metadata或忽略差异得到。
