# M8 声明式波次与 fragment 时间轴

这批实现是可运行、可检查点恢复的 V2 **模型**。原生 Scheduler 正文尚未恢复，`managed_clear` 和负超时策略没有客户端校准，不能据此将 0-11 或 36 关正式验收标为通过。M6/M7 源文件、内容与旧证据保留。

## 通用接口

`ark_sim/domains/timeline.py` 提供 `TimelineSystem(context)`、`handlers`、`start()` 和 `entity_retired(ref, reason)`。共享 API、Compiler/schema、Lifecycle、Movement 和规则接口由 root 整合；本实现没有关卡或敌人 ID 分支，也没有 V1 运行时依赖。

`scenario.timeline` 与非空 `scenario.waves` 互斥。时间轴必须声明 `policy: managed_clear | time_only` 及 `negative_timeout_policy: wait_for_clear | skip_wait`。每 wave 声明 pre/post delay、max wait、fragments；每 fragment 声明 pre delay 与 spawn/effects actions；动作声明相对启动 delay、重复 count/interval 和托管阻塞标志。

可变状态全在 `system/battle.components.state.timeline`，包括 phase、wave/fragment index、起点、remaining_actions、members、gate_start 和 wake token/time。完成状态为 `phase: complete, done: true`。API 注册回调后、battle/initial entities 建立后调用 start；start 预先计入全部实际计划出生数量。Lifecycle `spawn_wave(..., count_pending=False)` 返回真实运行 ID，成功出生才递减 pending；退场回调同步释放 canonical ID 成员。Lifecycle 的完成计算同时要求 timeline complete，因此没有敌人的尾部控制动作或 post delay 不会被提前完成。

## 显式时间与清场模型

- wave_start 为进入 wave 的逻辑 tick，位于 wave pre delay 前。
- fragment_start 为 fragment pre delay 后真正开始动作排程的 tick。
- action_start 为该动作首次重复的 tick。后续重复保留同一个 action_start，不改成每次出生的时刻。
- 每个出生实体保存 `spatial.timing_origins = {play_start, wave_start, fragment_start, action_start}`，原生 wave/fragment/action/repeat 索引保留在输入 parameters。
- 同一 fragment 所有动作并行按自己的 delay/interval 排程。所有重复动作完成且该 fragment 的 blocks_fragment 成员清空才推进。managed=false 的出生不得声明阻塞。
- 最后 fragment 完成后进入 wave gate。`time_only` 忽略 wave 托管等待；`managed_clear` 等待当前 wave 的 blocks_wave 成员退出。managed 但 blocks_wave=false 的活实体不会阻塞下一 wave。
- 非负 max_wait 从 **进入 wave gate** 起算；0 可立即超时。负值只允许 -1，含义由显式 negative_timeout_policy 决定，不声称还原原生 -1 的含义。
- gate 释放或超时之后执行 wave post delay，再开始下一 wave。后续 wave/fragment 起点来自实际推进时间，不能继续使用旧平铺绝对时间。
- phase0 退场可同 tick 推进；晚于 phase0 的 movement/lifecycle 退场在下一 tick 的 phase0 推进，避免向已过去的调度 phase 插入任务。这是一条明示的离散调度模型边界。
- STORY/提示 effects 同步完成，没有虚构 UI callback membership。原始 managed/dontBlockWave/blockFragment 字段保留在 action metadata，headless completion policy 明示；未来原生异步控制驱动仍需要单独接入。

## 0-11 新组合产物

`tools/build_m8_mainline_00_11.py` 从未改动的 M7 作者流程和 `sources.00_11.reference.json` 构建新 `packages/campaign/mainline_models/level_main_00-11.m8.json`。它严格检查 37 次出生的定义与 routeIndex，一条也不丢；保留六种 prefab 攻击包、真实 map/routes、options/seed 与现有单位闭包；STORY1、DISPLAY2 从平铺 scheduledEffects 移入各自 native fragment，并保留确切原始命令。未知 action 直接失败。

STORY 使用已冻结的 headless ack 效果。DISPLAY 原先平铺在 46/47 秒，对应 wave1/fragment0 delay27/28；M8 中这两个时间随真实模型 fragment 起点移动，而不是永远钉在46/47。不填空原生 predefines/runes：已有作者流程会拒绝未经转换的非空特殊内容。

routes13/14 的 `WAIT_CURRENT_FRAGMENT_TIME` 保留 type/time 原始数据，不替换成到达后 sleep。默认 `movement.wait_deadline` 以出生实体捕获的 fragment_start 求绝对 deadline。审计的平铺例子 S=54 秒时 S+30=84 秒；managed-clear 模型中 S 由前波真实模型清场决定，84 不是固定常量。原生 SchedulerSnapshot 和 checkpoint 类的字段、空正文局限见 `M8_FRAGMENT_WAIT_AUDIT.md`。

新包 manifest 的 schedule_profile 明示 managed-clear、负超时、起点与 post-delay 模型选择；source identities 锁新 builder、冻结 M7 composition builder、native source 与 controls SHA。`model_validated=false`、`formal_mainline_approved=false` 保留。成功 Compiler 并不等于客户端执行一致，也不等于整关已运行成功。

## 实际验证

2026-10-02 使用项目 `.venv` 的真实 Compiler/Engine 运行 `tests_v2/test_m8_timeline.py`：**24 passed，4.33 秒**。没有替换原生驱动为测试假回调。

独立预期覆盖波/fragment/action 原点与重复别名、managed 死亡/出口/撤回释放、非托管成员、fragment 阻塞、两种负超时策略、非负 timeout 从末动作起算、提前清场使旧 timeout wake 失效、控制尾部防提前完成、S+30 等待、phase0 同 tick/晚 phase 下一 tick 推进、空波/零次动作、严格未知/冲突声明、37spawn/3control 源清单，以及完整 checkpoint/replay 一致。

失败反例实际经过两次 placement 随机采样后触发 create 资源 bounds 拒绝，检查随机序列、别名、membership、pending 和动作完成量回滚。另一反例执行 input lock 与 emit 后故意触发不存在资源失败，检查控制状态、事件与动作进度回滚。Kernel 保留 failure 诊断并拒绝再次 advance；没有把任务 pop/fail-stop 状态错误声称成可继续会话。

新 builder 实际生成与 `--check` 均成功，Compiler **240 definitions**。本批没有整关正式通过证据、客户端 Scheduler 方法体或审批收据。

另对新 0-11 模型实际 advance 181 ticks：两次真实敌人出生、pending35、phase fragment_wait、四个 story.command；只是前缀 smoke。该运行 runtime fingerprint 为 `4628b3ea3e61e59c8caae0039ce08b91e6914bf9d3e04fbc5e667d1042cd5ecc`，运行时 implementation digest 为 `8282cb52bc64507b8b3fa6bfbe181d11905cbb97d544dd8dc997084988ab66f8`。这是终局修复前的历史源码身份，不覆盖 M7 旧结果，也不是整关成功。

## 终局独立复核与修复

同日新增真实反例：时间轴 t0 effects 消耗最后一点 life，Lifecycle 判为 defeat；旧实现 t30 仍执行未来 DP+9/input_lock，t60 spawn_wave 返回 None 后 action 抛异常。这是实跑失败，不是原生政策推断。

修复后 signal/action/退场通知首先检查 battle.finished，取消本系统所有尚未执行的 signal/action tasks。已失败的终局保留 result、finished_at、未出生 pending_waves 和 remaining_actions，不把取消伪装成成功；timeline 记录 `phase: stopped, done: true, terminal_result`，发出一次 timeline.stopped。终局在下一个本系统回调时收束；不能再执行它的对战资源或输入锁效果。不会取消其它系统任务，也不改变 Kernel 的失败诊断约定。

最终 fresh **25 passed，4.33 秒**，新反例同时验证终局前检查点恢复、继续 advance 和完整 replay 三者完全一致。builder `--check` 仍通过240 definitions，新内容包不变。最终 implementation digest `be41144c59f26182f4900477311b3b3c7f4a8518489257edea7181e5d307976a`；timeline.py SHA `441d9ee415715f9eb5a9b5cb552e6cc8d8980f9942897b46284f2a78393d0557`；test SHA `a01b4d8f77c0fd9035c24df6a64fb78760f6abfc7424c257cc3170cae71ddcca`。上述24项/旧smoke身份继续作为历史记录，不重标到此身份。

## 旧成员退场抢占延时：第二次独立反例

root 只读复核提出后实际运行：wave0 timeout .1秒，post1秒，wave1 pre1秒，当前模型动作应在 t63（2.1秒）。旧 wave0 成员在 t6 退场，旧代码提前唤醒 wave_post，动作实际 t36；在 t42 退场则绕过 wave pre delay，动作实际 t42。加 fragment pre1秒后动作应 t93，旧成员在 t72 退场却令动作直接 t72。三个用例先实跑红，严格原预期不变。

修复仅限制 `entity_retired` 的推进唤醒：释放成员必须属于当前 wave，并且当前为 wave_gate 且该成员 blocks_wave，或者当前为 fragment_wait、同 fragment 且该成员 blocks_fragment。其它 phase 仍更新 membership 并保留 member_released 事件，却不会覆盖已排定的 post/wave-pre/fragment-pre 延时。time_only 对照分别严格保持 t60/t90，未引入原生政策猜测。

最新 fresh **31 passed，5.02秒**；builder `--check` 240 definitions 仍通过，内容包不变，checkpoint/replay 与终局反例同步重验。最新 implementation digest `40846f2ed2d0b27b8090d78f2adae83e902a8768239312b630adbe93dd2e9a94`；timeline.py SHA `19fb4067f6a6569e986f1b03438452c21ccd7a28603a1df4f4e12bb684089672`；test SHA `63d5e21e1ca4983c2229b3d4f2e31720e6e3a3f3eccdf19f841091564035ab78`。前一节25项身份也是历史修复证据，不能重标为此身份。
