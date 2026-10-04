# M11 候选：Buff变化同步阻挡关系

候选根为 `D:/Arknights/Arknights_timer/unpack_work/campaign_m11_block_sync_candidate/ark_sim`。从冻结c0逐字节复制后，仅修改该副本的 `domains/buffs.py` 与 `domains/movement.py`。primary、c0/f6bb和旧candidate完全保留，没有提交或提升源码。

base implementation为 `c0b92545a714e763f3e43d4e13d25f0be99ecda912cb8479536982ac38f8216e`，候选最终为 `5b78616b961dbb4d0eda9276be68b8e2b37202b0267878255007921ad7e8712f`。正式可审阅差异保存在同目录 `M11_BLOCK_SYNC.patch`；源文件SHA与原/新actual module path、program/runtime fingerprint、测试日志及反例结果保存在 `validation/campaign/m11_block_sync_candidate.json`。

## 真正复现的问题

使用完全相同新content输入分别对冻结c0及候选运行；`tools/experiments/m11/base.c0.report.json` / `candidate.report.json` 保存两次实际执行，不覆盖原 `c0_myrtle_block_boundary.json`。

| 场景 | c0实际 | M11实际 |
|---|---|---|
| t0开始S2（还未阻挡） | 无敌攻击 | 无敌攻击 |
| t0已经阻挡，t1开始S2 | 敌人t1新cast，t19伤9.5 | 无敌人新cast、无伤害 |
| 敌人t1已cast，t2开始S2 | t19伤9.5 | **仍t19伤9.5** |
| 容量2降至1，显式再次blocking | 仍保留两名，实际超容量 | 保留一名，释放另一名 |

最后一项已经实际复现，源文件分析不再单独当作运行结论。曾提及的used双计仅是重写时的风险，不作为旧代码已证bug。

## 通用修改与事务

Buff apply/remove（包括phase0到期移除、aura child操作）在原outer atomic内检测声明的control.block或modifier属性。属性按ruleset的block_capacity/block_occupancy角色映射，不硬编码干员/敌人ID。相关变化同步调用Spatial.blocking；无spatial域的隔离Context默认不做同步。

Spatial.blocking现在自身atomic，并通过通用try/finally重入guard避免递归重算与异常后残留guard。每个旧关系重新执行blocking eligibility、on-path和剩余capacity检查，使用稳定实体顺序及旧blocker优先，每个成员仅计一次。容量增减即时释放或收纳成员；没有绕过替换的blocking规则。

自定义provider失败反例先实际draw `imp`、修改HP，再apply同时改变block_count/max_hp/atk的Buff，已经创建cast/事件/任务与资源容量同步，然后blocking失败。完整checkpoint（HP/resources、属性、Buff、RNG、tasks、events、关系、计数）与此前逐字段一致，且后续有效操作仍执行。另一个真实expression规则以 `1/0` 抛出RuleError，证明同样的完整事务恢复，并额外确认program/runtime fingerprint没有变化。异常未吞掉。

这些direct API失败probe只声明事务/检查点验证，不将人工调用Spatial.blocking或Ability.start冒充command replay。另有完全记录的Buff容量增减与到期命令、Myrtle S2命令场景，实际完整CP恢复和commands replay snapshot一致。

## 内容wrapper和攻击保留政策

新作者 `tools/experiments/m11/build_block_sync.py` 生成 `packages/campaign/mainline_models/level_main_00-10.m11_block_sync.json`，实际generate/--check通过。仅将Myrtle S2原timeline at0 NoBlock移到同步on_start，添加Buff.control.block=false，并令施法者取消自己尚未launch的普通攻击，以允许mid-normal S2开启。它不清理敌人casts，也不取消已经launch的包。其余原能力、配置与source保持。

真实来源是冻结skills.myrtle中的prefab组件pathID7458720872929114507：`astersi_s2[a]`、BLOCK_CNT5 / FINAL_SCALER3 / value0 / lifetime1等字段。on_start时点与“施法者取消未launch普通攻击”仍是显式可替换模型政策，原生FSM/body没有恢复。S2停攻沿用已有skill cast，不额外猜测动画动作。

NoBlock后**防止敌人据旧关系启动新cast**与**保留已started/launched攻击**分为两个独立case，不混为“所有攻击取消”。本批默认保留既有攻击；客户端是否需要中断的算法仍pending。

## 实际测试、冻结与范围

- 新candidate独立套件：**10 passed in 9.18s**，见 `tools/experiments/m11/targeted.log`。
- 既有domain rules / abilities / activation controls / buff mode lifecycle / spatial / flying / capacity兼容回归：**142 passed in 10.28s**，见 `regression.log`。日志首行与结束检查锁同一5b身份。
- 自定义holding_capacity角色、容量减增、Buff立即apply/remove、半开到期、重入guard、provider与expression失败、完整CP与commands replay均实际验证。
- exactMyrtle wrapper SHA：`af46aea8d1ffde0261ca777268ee69a3e8aa1adfecadb8e79adcc2246c5771c0`。
- patch SHA：`56cb286a74583fed221aac31f66242cebd3cab43a903aa650c6376b8c45674a6`。
- Buff候选源SHA：`9940289c1cb6d3655403a1ea6c9120240f23087a8e736d5dd6fa3b31a69bcb52`。
- Movement候选源SHA：`d72abc7132cc4caeb4499a66192324c240612ae586f7113496057d3fbd983eaa`。

已交roster agent用其原c0独立反例复核；对方结果单独保存，不自行生成审批。未执行整关，不升fullNPC/fullBoss或formal36。

已知后续空间投影问题：Grid._cell采用floor(x+.5)，部分selector/on-path仍使用Python round，半格tie可能分歧。本批不修改此投影或5b源码，M12须在新独立副本处理并保持circle连续距离及原生比较算法pending。
