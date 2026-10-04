# M8 0-11 fragment deadline 与 managed wave gating 源审计

本轮只新增本文档，不修改核心、builder、来源包、M6/M7文件或测试。
0-11组合包当前因未支持的checkpoint类型被Compiler严格拒绝，保持未运行；本报告不提供审批。

## 确证原始 checkpoint

锁源 `native_reference/level_main_00-11.json` 中只有两条非MOVE checkpoint：

| native route | cp index | type | time | 所属生成 |
| --- | --- | --- | --- | --- |
| 13 | 1 | WAIT_CURRENT_FRAGMENT_TIME | 30秒 | expanded waves[15]，wteeth，native wave2/fragment0 |
| 14 | 1 | WAIT_CURRENT_FRAGMENT_TIME | 30秒 | expanded waves[16]，wteeth，native wave2/fragment0 |

全部索引均为zero-based，因此wave2是第三个wave。两个单位当前flat模型生成时间同为57秒。
整份22条route的checkpoint统计为MOVE57、WAIT_CURRENT_FRAGMENT_TIME2；没有WAIT_SECONDS、
PLAY_TIME/WAVE_TIME、DISAPPEAR/APPEAR、PATROL、ALERT等其他特殊类型。

WAIT记录中的position(0,0)是保留的源字段，不能当作另一个移动目标。该检查点在第一MOVE之后、
后续多个MOVE之前，actor应在它当前停驻位置等待时间条件，而不是移动去(0,0)。
所有route `allowDiagonalMove=true`，三个visit flags=false；实际spawn routes为WALK，
0/7是未用于SPAWN的E_NUM占位。range幅度.1、offset0；reachOffset0、randomizeReachOffset=false、
reachDistance0。没有将任何特殊flags改成floor或普通路线来通过Compiler。

## Enum / snapshot / driver 来源

两份dump中的 CheckpointType均为：MOVE0、WAIT_FOR_SECONDS1、WAIT_FOR_PLAY_TIME2、
WAIT_CURRENT_FRAGMENT_TIME3、WAIT_CURRENT_WAVE_TIME4。
**类型值3与CheckpointTypeMask的bit值8不同**，不能拿mask8当type。
`Ark_data/dump.cs` enum见173886附近，current dump见172709附近。

确证数据结构：

- `Scheduler.SchedulerSnapshot`（dump420536）：FP waveStartTime @0x0、
  FP fragmentStartTime @0x8、float actionStartTime @0x10。
- `Scheduler`持有m_waveStartTime @0x90、m_fragmentStartTime @0x98，提供TakeSnapshot；
  Enemy.Spawn/Init和BasicCursor ctor都接收SchedulerSnapshot，BasicCursor持有snapshot @0x40。
- `BasicCursor.WaitCurrentFragmentTimeCheckpoint`（409977）有isReached、CheckReached，
  与`WaitForSecondsCheckpoint`（409884）是独立类型。后者另有FP m_time @0x20及Skip。
- `SchedulerDriver`（422540）持有main/sub schedulers，MAIN_SCHEDULER_IDX=-1，
  提供GetSchedulerStartFrame、DoScheduleMain/Sub等接口；不能将其他类的currentTime字段误认成它。

所有上述行为方法/iterator MoveNext仍为`{ }`空声明。结构和命名支持fragment-origin deadline
这一明确模型，而不是到达后sleep；但比较器、时间采样phase、pause、snapshot更新和实际
wave/fragment推进方法体尚未恢复，不能说已证明native完整驱动语义。

## 当前 flat 排程模型的绝对时间

当前转换规则用上一个fragment的最后一个action实例时间作为结束，叠加fragment preDelay、
wave pre/postDelay。它是**flat_last_action_schedule_v1模型选择**，不是原生managed gating证明。

| native wave/fragment | 模型开始 | 最后action时间 | 说明 |
| --- | ---: | ---: | --- |
| wave0 / fragment0 | 0 | 0 | STORY1 |
| wave0 / fragment1 | 2 | 17 | 敌人生成5/6、11/12、12、17 |
| wave1 / fragment0 | 19 | 52 | wave1模型start17，fragment preDelay2 |
| wave2 / fragment0 | 54 | 103 | wave2模型start52，fragment preDelay2 |

wave2/fragment0全部绝对动作关系：

| action index | 内容 | preDelay / interval / count | 绝对模型时间 |
| --- | --- | --- | --- |
| 0 / 1 | 两个wteeth，route13/14 | 3 / 1 / 1各 | 57、57 |
| 2 | slime_2 route15 | 5 / 10 / 5 | 59、69、79、89、99 |
| 3 | slime_2 route16 | 7 / 8 / 5 | 61、69、77、85、93 |
| 4 | slime_2 route17 | 8 / 9 / 5 | 62、71、80、89、98 |
| 5 | shdsbr route18 | 35 / 1 / 1 | 89 |
| 6 | nsabr route19 | 40 / 9 / 2 | 94、103 |
| 7 | shdsbr route20 | 39 / 1 / 1 | 93 |
| 8 | nsabr route21 | 44 / 1 / 1 | 98 |

所以本模型fragment-origin deadline为 **54+30=84秒**，1/30时钟下为**tick2520**；
wave origin52秒/tick1560、fragment origin54秒/tick1620、两个actor生成57秒/tick1710。
不能将spawn时间57替代fragment origin而算87秒，不能抵达后重新加30。
actionStartTime声明存在，但其native赋值方法体不可见；上表是模型动作时间，不声称已恢复它的赋值。

建议运行时保存每个actor的明确timing origins：actual model wave-start tick、fragment-start tick，
以及源wave/fragment/action索引。到达WAIT时deadline从**该actor捕获的fragment origin**计算，
不能使用当前全局fragment（actor可能还活着而scheduler已进入其他fragment）。
检查点/回放必须保存origins和deadline；缺origin时严格拒绝，不fallback arrival。

独立可审阅预期：fragment start54、offset30，arrival60等24秒；arrival83.5等.5秒；
arrival84或90不额外等待。deadline前被阻挡/控制不会把84重新延后；后续route replacement若需新snapshot，
必须是明确输入，不是隐式重启这个origin。模型可用半开`now < deadline`停驻、`now >= deadline`推进。
一般分数时间的量化需统一声明；本例都是整数秒，54tick1620+30tick900无舍入歧义。

通用authoring接口可保留原type3并规范为deadline wait，携带basis=fragment_origin、relative_seconds30，
或显式deadline单位2520及来源record；这应为通用时间basis，不能在kernel写关卡/敌人ID分支。
本轮没有实现或改动该接口，也没有把cp type3改成type1。

## 新 managed wave gating 机制缺口

原字段名为`managedByScheduler`，不是简写managed。确证 flags：

| 关卡 | SPAWN action行 / 实体数 | managedByScheduler | dontBlockWave | blockFragment | unharmful/alwaysKilled | wave maxTimeWaiting |
| --- | --- | --- | --- | --- | --- | --- |
| 0-10 | 17 / 35 | 全true | 全false | 全false | 全false | 单wave -1 |
| 0-11 | 20 / 37 | 全true | 全false | 全false | 全false | 三wave均-1 |

Scheduler确有m_managedWaveEnemies、m_managedFinalEnemies、waveCachedEnemies、managedWaveEnemies
property，提供ReleaseEnemyFromCurrentWave、FinishCurrentWave、SkipCurrentWave、TrackEnemyAtNextWave。
`Scheduler.<_DealWave>d__121`（420963）持有wave及nextWave，另有DefaultWaveHandler
WaitForPredelay/PostDelay/ExecuteActionQueue的iterator。这些声明说明必须单独审managed wave机制，
而不是把所有推进当作纯action列表。

**blockFragment=false不能推成“下一wave无需等敌人退场”**；dontBlockWave是另一个独立字段，
这里还是false。`maxTimeWaitingForNextWave=-1`究竟表示无timeout等清场、跳过等待，或其他sentinel，
当前方法体不可见，不能仅凭变量名指定一种含义并称native。
建议新增明确缺口：`native_managed_wave_completion_gating_not_converted`和
`native_negative_maxTimeWaiting_sentinel_semantics`。

本轮保留flat时间模型作为可审阅方案，但必须标“忽略managed inter-wave completion gating”，
绝不能升级为native已转换。0-10仅一个wave，下一wave门控没有当前后续wave效果；终局tracking仍是
独立机制。0-11三wave可能受此门控影响，所以54/84是模型时间，不能假称精确native绝对时间。

若下一阶段选择另一个显式managed-clear模型，应：在动作结束后根据声明的managed membership与
dontBlockWave决定可推进集合，退场/死亡/释放逐项更新；有timeout才按已选timeout policy处理，
-1策略需具名；wave/fragment实际开始时捕获运行origin S，本checkpoint deadline始终为S+30。
若wave1进入时间是T1、其fragment start为T1+2，则wave1最后action在T1+35；若wave2实际开始T2，
fragment start为T2+2，wteeth生成T2+5，deadline为T2+32。
不能一边使用动态managed门控，一边继续硬编码84；也不能未经来源证明把该managed-clear模型叫客户端行为。

## 审计身份与边界

| 输入 | SHA256 |
| --- | --- |
| native level_main_00-11.json | `f432d313e92466530cdf43d6b533c918b9237f9b0093a8b636511637f845975c` |
| 审计时未运行的level_main_00-11.m7.json | `78185a2e0c7e3b8d56e7a0d0d5e6e07b6d4566c2f1c7a41bdd2b4182137a2868` |
| Ark_data/dump.cs | `d25fb9fb7ec81253f112d9090e4550cd37a273ace56085d37610bb67c1e3a88f` |
| Il2CppDumper_current/dump.cs | `18c43dde9466317c45a786a0e4fa35cd8894d128592adda4394704bf99ea477b` |

本轮仅进行只读JSON展开、签名/字段检查，没有实际执行被拒绝的0-11，没有新增测试或改变
任何M6/M7身份、formal36状态。原生driver gating/clock方法体及客户端callback仍pending。
