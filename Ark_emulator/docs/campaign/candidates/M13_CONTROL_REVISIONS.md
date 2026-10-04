# M13 实际peer反例的两次独立修订

原419b、修订5fd、最终nonspatial18039三个目录分别保留，不覆盖历史失败/证明，也未合入primary。最终根为 `D:/Arknights/Arknights_timer/unpack_work/campaign_m13_control_nonspatial_candidate/ark_sim`，起止implementation均 `18039b0bc51c4aa5946cd41e16316085ac6d81783c70c5c4103667e61e702885`。

## 419b → 5fd：alias与终局

peer实际确认419b中alias=7会因startswith出现AttributeError；control on_start/step/on_complete修改life=0后仍可继续credit和completed。新5fd分支把alias的非空string/null校验放在修改前；非法alias以ValueError/公开command.rejected拒绝，checkpoint不变。

Control-owned effect每个有状态primitive之后经真实Lifecycle/objective rule结算，不硬编码life<=0。终局立即cancel controllers/stop timeline，嵌套emit/random child及后续targets不继续。on_start取消后不推进cursor，on_complete取消后不覆写completed；Timeline.action在终局不重排signal。未出生spawn人数保留。

`_settling_terminal`与`_cancelling`采用try/finally。非terminal on_cancel使终局时，停止后续普通序列并升级terminal取消；进入时已terminal的on_cancel finalizers可以清理自己的状态，任何失败仍整个outer事务回滚。实际表达式1/0前抽RNG、扣资源及跨两个control的取消回滚均实测；失败后真正ACK仍可继续。

5fd候选根为 `.../campaign_m13_control_lifecycle_revised_candidate/ark_sim`，身份 `5fd55fa7fd810138c5522e96a2e3842e7a925be58e7ff896392d3b96d5d45e93`。其216项定向/兼容测试全部过22.14s，source三故事两policy新身份generate/check及CP/replay通过。

diff patch `M13_CONTROL_TERMINAL_REVISION.patch` 是419b→5fd四文件差异，SHA `4096f6430c263d93d8de2d44fc3e8e9c73068baaa58c5b837dbaafea66d19148`。

工具复制过程中发生过一次输出路由错误：新wrapper第一次仍指向旧m13_profiles。发现后立即修为独立m13_revised_profiles，并用原419b/原builder重建及--check，再对照旧validation逐六文件SHA确认**全部字节准确恢复**。原419b核心从未改变。最终三套输出目录互相独立，不迁移旧证明身份。

## 5fd → 18039：无需空间的all selector

peer合法control effect.selector(type=all)+pure damage graph在5fd编译通过，但runtime强读system/battle.spatial.position，实际KeyError。新分支支持真正非空间all：标准provider无需source/target位置，Spatial.select两侧有位置时仍算原连续距离；无空间all用明确中性distance0评分，稳定ID规则选择。没有给battle虚构位置或ATK。

Control上下文需要空间origin的radius/grid/manhattan选择、source-centered area等在编译期明确拒绝；没有禁用所有selectors。actor-source空间契约维持原行为。heal/regenerate/push要求actor源，默认damage pipeline的source-ATK绑定也在编译期拒绝；显式source-independent pure damage.pipeline graph合法。effect级rules仍可替换，native comparator和无空间排序不是客户端证明。

真实多目标settlement不是mock：第一次graph实际分配target HP−10和battle life−3，引发死亡/defeat/cancel。第二目标HP10完全不动，只有一包damage.accepted，首tick末无control/timeline tasks，commands replay完整一致。合法空间负例、default source属性前提负例均是CompileError，不把运行fail-stop当能力边界验证。

最终nonspatial diff `M13_CONTROL_NONSPATIAL.patch` 是5fd→18039三文件差异，SHA `0991b41207093aa42ecf0244874acd35b920f53311ff9b28af7e9ee7b231baae`。完整变动SHA矩阵分别在m13_revised/m13_nonspatial的source.hashes.json。

## 最终选择、来源与peer证据

最终log `tools/experiments/m13_nonspatial/targeted_compatibility.log` 保存actual import、start/end同18039及 **249 passed in 22.09s**：45新/copy control/source/fatal/all-selector cases，加既有M8 timeline、ark import、domain rules、abilities、activation controls、Buff lifecycle、spatial、flying、capacity、M6 kernel review。没有全关长程或primary promotion。

新 `m13_nonspatial_profiles` 的external/immediate三故事均实际gen/check，真实gate/源flags/logical18秒/CP/commands replay通过。原419b和5fd内容证据保留历史；原生UI暂停/壁钟/确认/skip、NPC dormant registry、EMP和全关组合仍pending。

no-control同一legacy输入的program指纹、World、RNG、scheduler及全部390条events与M12逐项准确相等（此fixture无需selector）。其他空间/效果兼容由上述实际回归限定范围，不将这一样本夸大为所有代码等价证明。

roster agent已经用同一18039实际路径独立执行原9+fatal5+extra4及6个context negative全部通过，含跨取消失败完整回滚后真ACK继续、首draw停止、public badalias和真实首packet终局。其报告由该agent单独封存；本文件不生成审批。

| 最终新包 | SHA256 |
|---|---|
| model.external.json | `e5825129403a6869af2e079feeef8d6f8755dded8713811dbeba64c681c984c3` |
| model.immediate.json | `40752fbefedc9d52f5b0f36115b9c583907736e0379f2d083ad056a3cc16dd00` |
| assertions.external.json | `34b02485880b21bf663ca98e89a03ac7b5e3a3c4ddf54971389cf44ffe6f0809` |
| assertions.immediate.json | `a40417d1e8c0f3329fa91b44c396955681d8e43fa4c560b01974ccb1fce84af4` |

所有核心/包/源/日志最终SHA与明确scope写入新的validation报告，不重写旧报告。未提交/推送、不签receipt、不升formal36。
