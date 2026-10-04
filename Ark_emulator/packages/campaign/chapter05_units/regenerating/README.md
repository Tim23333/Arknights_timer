# 第5章常驻回血敌人作者模块

本模块仅包含 `enemy_1044_zomstr@0/d7a3f2fb16740407` 与
`enemy_1043_zomsbr@0/645365ece3e81647`。
它们分别绑定原 DB 的 HP恢复200/s、80/s，HP上限6000、2500，
ATK500、250，DEF130、100，OnAttack26、12帧，攻击间隔3s、1.8s。
单位、能力、选择器与规则使用独立 `ch5/regen` 命名空间，
没有把持续回血敌人套进 `ordinary.reference_model.json`。

运行核心固定为 M94：
`cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7`。
本模块使用已有 ResourceSystem 和 `resource.recovery` 契约，未修改该核心。

## 实际消费者

`hpRecoveryPerSec` 保存为 `hp_recovery_per_sec` 属性。
HP资源的连续恢复规则每个逻辑tick读取有效属性，计算
`current + hp_recovery_per_sec * quantum`，通过既有资源边界按当前
`max_hp`钳制。actor inactive或dead时恢复系统跳过；满HP暂停恢复，
受击后下一逻辑tick继续。没有额外SP、技能、重复静态recovery_rate驱动。
`mutant`标签保留，为后续源光环目标筛选提供数据。

普通攻击保留单MeleeAttack槽、source OnAttack、物理scale1、
blocked target路径、捕获目标、hit时属性读取与默认攻击间隔。
本模块显式声明 windup=`OnAttack秒数 / max(有效ASPD比,.01)`，
攻击间隔沿用通用time.interval。原始ASPD100下命中源26/12帧；
动态ASPD与原生动画缩放clamp/callback方法仍需要客户端校准。

构建器对固定SHA、精确level0/无override、无skills/talent/passive、
无附加动画驱动、无第二attack/trigger槽、无activeBuff/额外伤害、
无born延迟/通用能力/特殊阻挡条件及未知组件明确拒绝。

## 作者验证与独立审核入口

`tools/chapter05/tests/test_regenerating_units.py` 的34项作者检查通过：
逐tick/1s/2s明确数值、饱和和分数余量、受击、致死精确边界、
休眠激活、暂时inactive且无catch-up、死后不回血、不复活、
有效回血属性修饰、原攻击帧与快/慢ASPD间隔、四变体组合隔离、
真实磁盘CP续跑与公有replay，包括未激活、攻击inflight和已死亡状态。

`packages/campaign/chapter05_reports/regenerating/author.evidence.json`
保存两种独立可重编译probe、真实落盘CP、replay、完整JSONL日志，
及forward/CP/replay的snapshot/events/continuation_state观察。
两例在tick20激活、tick30承受100物理伤害、tick60终点HP分别
1166.6666666666667与1006.6666666666667，三路径全部一致。
独立审核者可使用probe文件在固定M94重编译并复验这些保存的证据。

## 来源政策与边界

固定来源 `chapter05_sources/native.reference.json` SHA：
`323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5`。
DB/关卡提交固定为 `56aee3d6c5a29c3a0d192456d70d14252cbb0804`。
本地prefab/Spine闭包保留自身SHA；它们与该表提交及现客户端的版本对齐未验证。
本模块不使用旧外部token参考包。原生body separation/selection collider、
steering arrival .05、动画scale/clamp及完整攻击FSM方法校准列为明确边界。
Mephisto光环、其余第5章机制和完整关卡组合属于后续依赖。

`formal_approved`、`independent_reviewed`、`whole_stage_executed`、
`actual_client_verified`均保持false。本交付为作者模块和可复核证据，等待独立审核。
