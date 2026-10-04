# 当前波次显式完成请求

第七章原始 `FinishCurrentWave` 节点以 Buff owner 为来源，参数为
`finishAndSkip=false`、`trackSourceAtNextWave=false`、`trackSourceAtWaveDelta=0`、
`trackAllManagedEnemiesAtNextWave=false`。完整来源需求见
`packages/campaign/chapter07_boss/patrt/release_wave.requirements.json`。
现有 `entity_retired` 只能在真实退场时释放 managed 成员；Boss 复活等待时仍存活，
不能用伪造死亡、删除成员或 `advance_branch` 代替完成当前波次请求。

拟增加内容效果 `finish_timeline_wave`，限定目标 `source` 或 `self`，参数须完整声明：

```json
{
  "op": "finish_timeline_wave",
  "target": "source",
  "parameters": {
    "finish_and_skip": false,
    "track_source_at_next_wave": false,
    "track_source_wave_delta": 0,
    "track_all_managed_at_next_wave": false
  }
}
```

第一版仅消费以上精确组合。布尔字段要求严格布尔，整数偏移要求严格整数 0；
未实现的 true 分支明确拒绝。调用源必须是当前时间线中当前波次的实际 managed 成员，
含活动或等待复活且仍存活的同一单位。一般场景无时间线、其他波次成员、退场实体和 battle 实体不能发出请求。

请求记录在当前时间线状态，绑定波次编号、source ID、生命周期代次和调用时间；相同波次重复请求幂等。
按明确参考策略：不跳过当前与后续碎片的预定动作，不取消尚未出生的敌人、不强制完成用户确认控制，
仍等待动作调度和当前阻塞碎片控制完成；进入当前 wave gate 时忽略该波次的敌人清空条件，
保留控制完成条件、原始 postDelay 和下一波 preDelay。

原 managed 成员仍保留所属波次与真实生命周期，不把它们转移到下一波。
后续怪物仍按原行动诞生，所有活敌仍由战斗结束条件检查；请求不会修改 kill、leak、HP、pending 出生或路线。
实际退场继续释放原成员，不干扰其他波次的等待任务。

调用与任务唤醒为一个领域事务。发出完整审计事件，包含 source、wave、原 phase、实际调用代次和参数。
未完成阶段、已经处理的 postDelay、旧回调或战斗终局不得取消合法未来任务或重复完成波次。
检查点保存该请求，磁盘读回和从头公开重放必须得到相同的调度与事件。

必要验证包括第一阶段 HP0 复活等待、仍存活友军与延迟出生、两波不同 post/preDelay、
重复请求、非当前源拒绝、控制阻塞、晚回调、故障回滚、所有出生守恒和原 actor 保持活着。
该策略缺少原生方法体证明，作为可替换参考规则实现；来源指针、原始参数和未实现分支始终保存。
上述约定作为隔离原型的参考策略；正式底座与关卡完成状态不由这份设计改变。

已新增隔离原型 `campaign_finish_timeline_wave_v1_candidate`，身份
`b38f69037b81c3de7f207d748ed22a0463a233af2c546c70632dd8069fab6932`，父版本为第七章联合7696。
10 个作者边界与36个旧时间线／资源回归共46项实际通过，含真实磁盘检查点与公开重放、HP0复活等待源、
晚请求拒绝事件、公开控制确认、故障回滚、原始延迟出生与post/preDelay。
原型未推广，真实来源 Buff ON_FINISH 消费、独立复核、完整回归及基线仍需生成其自己的证据。
