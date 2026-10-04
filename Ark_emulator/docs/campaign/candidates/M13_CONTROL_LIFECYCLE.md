# M13 独立候选：通用异步control lifecycle

候选根 `D:/Arknights/Arknights_timer/unpack_work/campaign_m13_control_lifecycle_candidate/ark_sim` 从冻结M12 bd60复制。旧branch、primary、旧包/证据完全未改。最终implementation为 `419b3c706820597d6d5b9f012e5a4caa33ea0adfd9ca1a62dbf2151566895df2`。

## 声明接口

新增package collection `controls`，kind=control。字段：

```json
{
  "id": "control/model_dialog",
  "kind": "control",
  "clock_policy": "logical",
  "ack_policy": "external",
  "on_start": [{"op":"input_lock","target":"battle","parameters":{"key":"dialog","enabled":true}}],
  "steps": [
    {"kind":"effects","effects":[{"op":"emit","target":"battle","event":"model.observation"}]},
    {"kind":"ack","key":"dialogue/1"},
    {"kind":"delay","seconds":4}
  ]
}
```

clock只允许logical，ack必须external或immediate。effects、delay、ack按有限step顺序执行；ack key必须唯一非空。delay须有限非负，复用现time.quantize。不新增numeric contract。control owner级rules尚不支持且严格拒绝，可在各effect显式绑定现有rule。内嵌schedule严格拒绝，使用delay step，以防未归属的异步jobs脱离lifecycle。

Timeline增加kind=control action，字段definition、instanceAlias可选、delay/count/interval/managed/blocks_wave/blocks_fragment沿用声明含义。它与spawn/effects互斥；refs严格匹配control kind。旧sync effects接口不变且仍不能伪装managed membership。

外部输入为 `Simulation.submit({"action":"control_ack","control":"story/alias","step":5})`。control为runtime ID或本实例alias；step必须当前waiting的整数cursor。只control_ack绕input_lock；额外source/ability字段、矛盾type、未知实例、错step/phase、bool和重复ack均拒绝。没有公开skip/cancel命令；原HEADER skip字段仅source metadata。

## World状态、门与计数

control实例在World保存pending/running/completed/cancelled、phase/cursor/generation、origins、start/delay任务ID和锁。pending在fragment展开时创建，start任务归属实例。未启动控制仍由remaining_actions保持fragment；开始时先登记control_members及action消耗，再同步执行on_start，故immediate completion也正确释放。

真正完成所有steps和on_complete后才写completed、清自身jobs/locks并通知Timeline。发一个`control.completed`事件本身不改变状态或释放门。controls不创建actor、不增加enemy、kills/leaks或pending_waves；后者仍只统计尚未spawn的实体。member释放只唤醒所属当前fragment_wait/wave_gate，不破坏已排post/pre delay。

control计时完全logical，敌人/资源/战斗继续推进，不隐式暂停游戏。原生wall-time、暂停、动画等待和UI确认仍client_pending。managed_clear/wait_for_clear用于本批来源fixture；其它Timeline timeout/time_only政策仍是显式数学选择，不能称native scheduler body已恢复。

## 实例拥有锁和取消

control effect执行携带内部instance marker。input_lock实际key为`control/N:raw_key`，World记录每个实例自己的锁。两个control使用相同raw key也彼此独立；完成/取消只能解自己的key，全局普通锁仍保留。配置control时`control/`全局锁key及alias前缀保留给runtime；无control配置保留旧路径。

非terminal内部cancel必须显式policy=continue，取消自己的start/delay任务、清自己的锁、状态cancelled，不发completed。pending cancel还消费本action remaining计数，使后续fragment按声明继续。terminal cancel需要真实finished，取消pending/running实例并同步停止Timeline任务，未出生spawn数量保留为中断证据。

Lifecycle的finished写入和全部control terminal cancellation在同一outer atomic中；若on_cancel失败，先前控制的清理、finished状态、锁、RNG、jobs和events全回滚。不存在按角色ID、剧情文字或关卡号执行的内核分支。

## 实际失败与恢复语义

独立on_complete expression `1/0` 失败前实际draw imp并改life，完整checkpoint恢复一致，实例仍running/awaiting、门未释放。失败begin还原pending、锁、资源和jobs。terminal on_cancel第二实例失败时，第一个实例已经进行的取消以及finished标志一并回滚。

handler失败遵守既有Session fail-stop：domain事务恢复World/资源/状态，kernel保留failure诊断，进入handler前已pop的任务不伪称可继续。测试确认再次advance拒绝，并从此前valid checkpoint恢复完全一致。direct API失败probe只证明原子性，不冒充记录命令回放。

## Chapter01 source-aware新wrapper

新 `tools/experiments/m13/build_chapter01_control_profiles.py` 读取冻结Chapter01 control source（SHA `caa25dcdfbb2af5707a4d0d9ec86e8c73feec38fefdaad9481b5aa3df1ecc79a`），生成 `packages/campaign/chapter01_controls/m13_profiles/` 的external/immediate两套新source/model/assertions。旧source、model、helper均未覆盖。

每个source action模板保留原wave/fragment/action、count/delay/interval，以及managedByScheduler→managed、blockFragment→blocks_fragment、dontBlockWave反向→blocks_wave。HEADER/name/dialog/Popup/Delay/Blocker所有行与UI文字保留，文字仅metadata；dialog/Popup产生声明ack步骤，Delay产生真正logical delay。

1-11_a external模式实际停在cursor5等待dialog ack，30刻仍在fragment0、没有next_fragment；成功ack后完成并进下一fragment。1-11_b source blockFragment=false，故同wave下一fragment可提前执行，但blocks_wave=true，实际wave_gate保持到540刻（源Delay总和18秒）完成，下一phase0在541刻推进。Popup实际0/120/240/360/480刻。没有用native.story.finished绕门。

Immediate profile不声称原生autoable或skip，明确是headless数学ack。真实STORY_a/1-11_b/1-12三故事在两profile下均实际CP/commands replay通过。1-12 EMP、NPC dormant registry、固定12/nativecards组合及完整敌人/关卡依赖仍pending，未称整关已可运行。

## 测试选择与起止身份

`tools/experiments/m13/targeted_compatibility.log` 保存实际M13路径、start/end同419b身份及 **202 passed in 17.92s**，明确选择：22个新control cases、M8 timeline、ark_import、domain rules、abilities、activation controls、buff mode lifecycle、spatial、flying、capacity。

新source suite `source_cases.log` 另有 **3 passed in .50s**，共205不同cases，不伪称一次205-case命令。新两profile generate / --check实际通过。

no-control同一旧sync-effects输入分别在冻结M12/M13执行：program fingerprint `1d8158d61f8e946ebaba81a3f4cdbb1a42ad650db26fd0c0478e5bad444e4e9f` 相同，World、RNG、scheduler和全部390 events逐项完全相等；无controls空字段、control events或默认tick/tasks。结果保存 `tools/experiments/m13/no_control.{m12,m13}.json`。

按Root要求仅复制离线 `ark_emulator/levels/packs/level_main_00-01.json` 到候选对应路径，SHA `f71299c156d27a03d849115df49bd53c1abff79497f233e3266dde1988f6d6fa`；没有复制或导入V1 Python。硬绑定候选的测试均在tools/experiments，避免进入primary全套收集。

## 冻结审查产物

patch `docs/campaign/candidates/M13_CONTROL_LIFECYCLE.patch` 是bd60→419b的11文件差异，含新controls.py；SHA `2b2713511a8584c8c395874f836c460b72d1bdaac5100a07352fd4f18c7e20bc`。逐文件前/后SHA保存在 `tools/experiments/m13/source.hashes.json`，完整log/source/package矩阵另存validation报告。

| 新内容 | SHA256 |
|---|---|
| model.external.json | `79deca85869ff4490b4a47abbd4cb6f324dea6468d5ed32efe46d0abd87af706` |
| model.immediate.json | `85d81d149bb4e9ec303fbcb9649ce12e7ca661a1eabf1de8444e2cac10f05abf` |
| assertions.external.json | `ba2b508210923dc42b3c668a177eaf3e5dffbc61328bf1ece9c9cf2ada32f12e` |
| assertions.immediate.json | `bb08ea12f1b36cc1eb5f8f429731c0ddab3e562271bd77a7f2c2f8be10ade50a` |

核心419b冻结供独立复核；未合入primary、未运行全关、未签receipt或提升formal36。
