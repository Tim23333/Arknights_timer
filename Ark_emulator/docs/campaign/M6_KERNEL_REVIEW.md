# M6 通用内核独立复核

2026-10-02。本轮仅新增 `tests_v2/test_m6_kernel_review.py` 和本文档，保持攻击侧四文件冻结。
没有修改 `ark_sim` 或其他作者文件，没有提交/推送。以下是实际模型合同复核，不是原生客户端
算法、时钟、来源版本或三十六关正式验收的证明。

## 实际发现与修复

| 问题 | 独立反例与原结果 | 修复后实跑结果 |
| --- | --- | --- |
| 额外包丢失作者的 hook locks | A source hook 的 child 显式声明锁 B，core 覆盖成 `{A}`，child 又触发 B。 | 合并 child 原锁、继承锁和产生 child 的 source Buff；不会出现 B 的不期望事件。 |
| 混合 alias/sentinel allocation 覆盖同一资源 | 同一个 target 的 HP 分配为 alias `target1:-10` 和 sentinel `target:-5`，receiver factor2。应扣30，但原实际 HP100→90；alias 项未缩放，两个独立 plan 还互相覆盖。 | base settlement 在 after hooks 前 canonicalize；每个 after 输出再次 canonicalize，最终分组解析。HP100→70、shield2→1、damage_dealt30、accepted amount30，graph events 保留。 |
| 免费 owned spawn 伪造已付款费用 | DP0、无 activation DP cost 的免费 spawn，child raw deploy_cost10，却被 record 成 paid_cost10，可撤退凭空返 DP。 | 免费默认 actual paid_cost0；付费需显式认领 cast 的实际 battle 部署资源付款，不能把估算部署费用或同一笔款复制给多 spawn。免费生成/撤退 DP始终0。 |
| direct effect target alias 漏计实际伤害 | 支援作者独立找到 target alias 直接传入 execute 时，HP已扣、accepted amount及 damage_dealt却为0。本 suite 的原 helper 提前 resolve，未覆盖此入口。 | 增加不经 helper resolve 的独立用例：direct `['target1']`，HP100→88，shield2→1，accepted amount和 damage_dealt均12，事件 target为canonical runtime ID。 |

前三项由本轮独立复核直接发现，root 修改通用实现。第四项由支援作者发现、root 修复，本轮添加
独立入口反例验证。旧失败结果没有重新标为原版本通过；原 locks 和 allocation HP70 预期没有放宽。

## 24 个独立测试的范围

测试使用真实 `Compiler`、`Engine`、调度、资源、世界和 RNG，没有替换内核 handler 或注册假 provider。
复用的基本 scene factory 只提供普通 source/target，所有复核规则、Buff、能力及断言均另行编写。

| 范围 | 可检查的运行证据 |
| --- | --- |
| damage hooks | child locks 合并；source extras 仅在主包真正接受后执行；无效高优先级 hook 不占 group、不耗 RNG；base/after 产生的 aliases 都在缩放前归一化。 |
| transaction/RNG | source extra 在主包结算后失败仍回滚主包、RNG、公开事件和全世界；第二 target after hook 失败恢复已经处理的第一 target及两次样本。 |
| settlement_scale | 只缩放本 receiver 的健康分配，shield charge保持原量；graph events不丢；多 allocation 合并后实际 damage 统计正确。 |
| clock switching | 新模式立即使用重置时钟，旧未 launch 普通包取消；on_start 中途失败恢复旧 cast、任务、next_attack、公开历史和旧包命中。 |
| emission snapshot | frozen 事件在同 tick finish后仍不能 grant；nested schedule 在后续 tick 仍继承该冻结状态；emission未冻结的 grant 不被 recipient 后来开始的 cast倒推为冻结。全部通过实际能力运行，未伪造 runtime cast记录。 |
| paid owned deployment | 一笔5 DP支付拆分2+3给两个实际 child，使用真实 `move` 腾格和标准占位规则；两个退款合计5，不能增钱。第二次认领导致3+3>5时，首个 child、move、付款和事件全回滚。负认领在 compile 阶段明确拒绝。 |
| shared deployment eligibility | 高台/地面不匹配、已有占位及容量不足在 owned spawn 的同一启动事务里拒绝，付款和状态不留半成品。 |
| healing override | ability 层显式 ignore_heal_immunity 的 selector 与实际 settle一致，免疫目标实际被治疗，避免只选中但又被 settle拒绝。 |
| scheduledEffects/input_lock | 两个不同 lock key 重叠，释放一个仍锁输入；同 tick释放最后一个先于 command，命令随后真正执行。定时随机效果失败不留下 lock、资源修改、事件或随机消费。 |
| restore/replay | 在三次具有随机 hook 的命令之间 checkpoint，恢复及完整 replay 的 snapshot相同，样本数/次序一致。 |

部署测试起初使用了内核内部支持但 public schema 未开放的 `displace` 别名，改用公开 `move`。
未扩大 capabilities 来让测试通过。自定义 overlap policy 被契约正确拒绝；最终多 spawn 测试直接
移动第一名实际 child 腾出部署格，保持真实标准 eligibility 规则。

## failure boundary 的独立判断

最初的新 scheduled failure 用例错误要求整个 `Session.advance` 前后 checkpoint相等。
独立阅读 `ark_sim/kernel/session.py` 的 `advance`/`_state_data` 确认：任务在进入 effect transaction前
已 pop，异常会保存 failure诊断并使会话 fail-stop。这是已经存在的正式 kernel行为。

最终测试仍严格要求 World、公开 events 和 RNG与效果执行前一致，但同时要求 failure诊断存在，
再次 advance明确拒绝，必须 restore有效 checkpoint才能恢复会话。没有将诊断或已执行调度任务
误称为效果内的半提交，也没有修改内核语义来掩盖异常。

## 最终运行与身份

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m6_kernel_review.py -q
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m6_kernel_review.py tests_v2/test_damage_hooks_random.py tests_v2/test_hook_groups.py tests_v2/test_scenario_effects.py -q --tb=short
```

独立套件：**24 passed，2.32秒**。联合既有相关套件：**35 passed，3.42秒**。
没有 skip/xfail。运行时 implementation digest：
`2ead42b3f048e1bcdcaffd78792e009a8db133b1aab43705e261ade692400321`。

| 复核时源码 | SHA256 |
| --- | --- |
| `ark_sim/domains/effects.py` | `fad10958514333f4590d77a7a38ffe2474f20412e150669c017aababad11d775` |
| `ark_sim/domains/buffs.py` | `80a5f4aec90be10407f3e81042312b7bc2b6c548392e956ebd0b1c822805e75b` |
| `ark_sim/domains/context.py` | `7e3804de9af96d70cd260a7c40ed741c616e2dce7fcbaf3de93db7df22ee54d9` |
| `ark_sim/domains/abilities.py` | `6b0d4767a71ce42b3291443ef7fd3d2ef206474fc5baa8ec8df87b7884b4594a` |
| `ark_sim/domains/deployment.py` | `8d6a2b85ca47fe653e73c7f09ce340cd690b18c53b78e474894ec7808931df95` |
| `ark_sim/domains/movement.py` | `18561f457ea0a95bb24207ae8ff1d31f7bcf6257badc596eb551b1dea68b48db` |
| `tests_v2/test_m6_kernel_review.py` | `c8fda7707b89ed9fc275ddd693425f2aaf7e684f5a4e13d1b0e340411b90957a` |

后续任一 core 源码变化都需要新的运行身份证据。此报告不改变既有模型/原生 pending，也不提升
任何正式 mainline case状态；原生 RNG消费、damage回调、攻击信号和动画/FSM时钟仍由来源/客户端
校准流程独立判断。
