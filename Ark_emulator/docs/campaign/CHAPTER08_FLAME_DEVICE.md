# JT8-3能量聚合体装置

原JT8-3预放置10个hidden `trap_021_flame`，等级1、phase0、favor0、potential0、skillIndex0／mainSkillLvl1。source保存fixed表与2025-03-27官方Prefab版本差异，不能把缺少本地同名Prefab当空Actor。

当前源消费者 [module.v2.reference.json](../../packages/campaign/chapter08_consumers/flame/module.v2.reference.json) SHA`ddb9686b18d559f9545592ebf55d016a6a3e3c46d922e6ba7f8ef51e480ae894`在7e76候选运行。原HP6000、ATK0、DEF200、RES20、block0、slot0、25SP／recovery1保留。装置激活后修改当前格buildable0／passable2／height.4，退场恢复原格；四弹道使用原speed2.5／radius.25／life60／maxHit1和unmanaged retainedsource，内核不修改caster位置／朝向来拼四方向。

`flame_s`源BSON先FixedValueDamage1000MAGICAL／NORMAL／ignoreSPFalse／skipModifierFalse，再CreateBuff dragon_fire。当前提供器根据当前目标RES结算固定法术包并保留afterhook，命中后使用动态灼烧父／子消费者；子数值BB50／180／30与30.5源skill小写键经明确字段映射，源原串保留。

两项真实作者场景已通过 [verification](../../validation/campaign/chapter08_flame_device_v2/author_source_v1.json)：自动SP25在当前浮点计时749触发（源25s字段保持，计时政策需复核），四ray758命中RES27目标各730，随后每target一包56灼烧，HP9214。装置已经withdrawn仍由原retained projectile执行。CP740落盘/SHA重载、续跑与head完整状态及事件一致。提前trueDamage6000使原6000HP死亡时无四ray。源自爆是withdraw不伪造combatdeath。

旧v1 payload写targetsource导致collisionhit后又选回旧device，真实0伤害失败保；v2只改collision-selected payload目标，未改变sourceStats／弹道／预期伤害。当前为装置机制范围，不批准完整JT8-3或原生Collider／client。

原bsnake_flame七phase多次激活同alias：每alias2–5次。现有注册只激活一次且退场后不能复用，已保存实际公有activate0、25SP发射withdraw749、activate780拒绝的 [反例](../../validation/campaign/chapter08_flame_reactivation_counter_v1/counter.json)，SHA`83940a39542e754a60d37fbc81961c5ef398b102829e0d246e629964533ec0ca`。拟增加显式有限`reactivation`配置：每次只在原实例退场后创建新的actor incarnation并更新registration key，保留旧actor给已发射弹道，重置原sourceHP／SP且不改变旧状态。新reuse候选仍需权限、预算、占位、回滚、CP/head及独立复核，不能删除重复phase绕过此项。
