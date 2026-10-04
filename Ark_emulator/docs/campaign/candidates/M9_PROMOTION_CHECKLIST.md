# M9合入检查清单

Primary core仍为M8 f8，原0-10命令回放与增伤修订0-10检查点/回放正在使用它。
当前候选最终身份为 `5a21fc5c6a51456c453a572cacee5c83e147a2d7a2615d5436d5cf9959ca00b9`，
位于 `../unpack_work/campaign_m9_final_candidate/ark_sim`。

## 合并内容

- 全局实例alias编译门：initial/flat/timeline/action重复suffix与reserved system别名。
- Resource public引用转为canonical actor ID，未知source在写入前拒绝。
- 内部Scheduler fork和next_task_id，公开checkpoint隔离/校验保持；cancel记录有界清理。
- 路线消失/出现、隐藏可选择性/效果/光环策略、非零reachOffset的两项显式纯规则。
- nullable随机标记兼容：None/缺失/False作为未定义；True/错误类型仍拒绝。
- 可见性查询作为孤立domain Context可选接口，完整RuntimeContext仍执行真实hidden策略。
- 规则catalog新增movement.transition/checkpoint_position，契约79→81；primary旧测试在实际合入时更新，
  候选测试副本已明确检查两个新增ID及不变性，未改原79断言后冒称旧测试通过。

## 已执行检查

旧cadd全套1143pass/10fail日志保留：9隔离Context接口、1旧catalog计数。
新的domain/routes/rules/fork/bounds142项实际通过。最终候选0-1全程/CP/replay及自定义850/60通过，
见 `m9_final_baseline_20261002.json` 与真实重建runtime匹配的identity JSON。
完整V2+最终候选全套与当前roster首关600tick前缀仍在执行，不提前计通过。

## 合入前必须完成

1. 保存最终全套退出状态、summary/log/SHA、candidate源码前后相等和确切测试选择。
2. 完成当前roster前缀的出生/命令/资源守恒、checkpoint/replay；保留候选scope。
3. 完成/保存仍使用primary f8的两个0-10恢复和回放结果。不能改源码中途使旧身份失效。
4. 对待合入文件逐份核对最终5a字节和补丁；不把旧39c/cadd/queue-bounds结果重标为5a。
5. 复制最终源码到primary后，更新79→81测试，并在primary实际复核身份和相应基线/完整验证。
   路径变更会影响provider来源定位等运行身份，不能只搬报告代替实测。
6. M10按能力冻结与精确中断仍是另一分支，先独立review与测试后再决定合并批次；
   不因其基于旧候选就覆盖M9兼容修复或漏掉queue-bounds。

文档、数据包和规则模型仍可继续开发，正式关卡审核收据另按七门验证。
合入底座不自动意味着完整干员或36关通过，也不代表已与客户端逐帧对齐。
