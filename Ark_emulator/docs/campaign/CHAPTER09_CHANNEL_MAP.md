# 逐格地图与技能时钟底座

2026-10-05 已推广的生产核心为 `f0c2944cc89788b9277cbafe55ba1d9dcbdfe1e2f29c3619ce3fd1da9a6b7e9c`。
它在 56f380 基础上合入九个文件，契约数量仍为106。
推广前，本候选自己的1219项完整回归、0-1与自定义公式基线、25项作者门均实际通过。
独立复核在同一联合身份上重新执行11项时钟／Flame和6项地图测试，共17项，十个实际磁盘CP／公有从头回放完整比较。
推广收据见 [promotion.json](../../validation/campaign/chapter09_channel_map_primary_v1/promotion.json)。

地图内容可以在 `map.tile_cell_mechanics` 中以规范的 `row:col` 键声明逐格配置，例如：

```json
{
  "1:6": {
    "type": "occupancy_buff_field",
    "definition": "unit/ch9/bigforce/field",
    "expected_blackboard": {"base_force_level": 1.0}
  }
}
```

它需要已有的原始逐格 tile 数据，并核对同格黑板；保留该格原来的 tileKey、类型、位置和黑板操作数。
声明的场域实体及Buff必须进入正常依赖闭包。没有逐格声明时保持已有地图行为。
当前逐格接口只接受已实现的 `occupancy_buff_field`；越界、非规范坐标、未知类型或不匹配黑板均拒绝。
第九章两关地图全部非空黑板的固定配置见 `packages/campaign/chapter09_consumers/pillars/native_maps.profile.v1.json`。

技能生命周期内容新增两种通用动作：

```json
{"op":"set_ability_cooldown","target":"source","ability":"ability/custom/skill","duration_seconds":10}
```

```json
{"op":"interrupt_ability","target":"source","ability":"ability/custom/skill"}
```

目标必须实际拥有声明的能力。冷却先通过该能力及效果局部作用域的 `ability.recovery`，
再通过 `time.quantize`，因此数值算法继续可替换；中断只取消该能力的cast、任务、所属Buff及连接。
生命期关联要求能力已存在于实体依赖闭包。能力与所属Buff之间的冷却／中断引用不会误判为递归构建，
真正的 `trigger_ability` 循环和缺失引用继续拒绝。字段与时长同时受静态、运行时验证。

no-opt-in兼容审计发现新增协议改变了program metadata中的可用effects列表，
因此program与runtime两个顶层身份字段变化。完整差异定位证明除此以外，
scenario、definitions、rules、ruleset、依赖、kernel状态、任务、RNG、事件和attribute cache全部逐值一致。
原来只忽略runtime身份的失败报告保留；新的身份封套门只分离已证明的两项顶层身份，
没有过滤cached、context、value或cause。详见 [身份审计](../../validation/campaign/chapter09_cell_fields_peer_joined/nooptin.identity.envelope.json)。

本次推广完成通用接口。Flame施法状态与双包仍是原型，完整焚毁者的触发、范围、重复政策和死亡爆炸链需要继续实现。
精确HP0延期、柱体受击倒塌桥仍为独立候选。第九章整关尚未验收，客户端准确性继续单独记录。
所有已完成测试的大日志已按用户政策清理，精简身份和结果收据保留。
