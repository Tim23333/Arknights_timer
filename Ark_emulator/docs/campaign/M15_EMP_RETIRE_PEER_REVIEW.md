# M15 EMP技能/通用retire slice独立复核

本次只读原177ede退场候选及新f98a分类候选，未改其源、作者测试、旧EMP包或primary，不签promotion/主线receipt。原177/98f报告保留，新f98/79ed另出证据。Terrain overlay始终是未实现依赖，不能称完整EMP。

## 原生字段与原slice

实际读dump和serialized source核SideType ALLY1、EntityCategory DEFAULT1/TRAP_OR_ITEM2、INVINCIBLE5、STUNNED0、AbilityStandard.Event ON_CAST_END3、FROM_OWNER1/BEFORE_SPELL_START1；MeleeAttack.selector PPtr确指AdvancedSelector。E0L10从真正两端frames用Fraction线性得到HP100/ATK1000/basecost5/block0。初始SP0/cost5/TIME1、额外DP10、官方pin x-4九格3×3、native pos(2,5)→8rows top(5,5)/UP/aliasNone均直接核源。

.75指定predelay量化23tick，1.5 finish45tick是明示model callback clock，不宣称恢复native方法体。攻击type2由原enum映为arts、atkScale1；active buff STUNNED0/durationKey stun→源BB7秒；ActionToOwner一次ON_CAST_END、Withdraw force/switchDead为真实ability.finished订阅后op retire reasondead。INVINCIBLE实际receiver after hook拒绝三个伤害通道，不是只写不可伤metadata。

原slice独立7项通过：150技能→173packet（23）实际重选进场＋对角两目标各800/RES20，离场目标不伤；195finish事件之后真正退场，HP100保持/noCombatKill；383 stun半开到期。三通道incoming与SP/DP原子付款失败、160withdraw取消173packet/195finish、无lifecycle实体retire、enemy reasondead计1但HP80保持不combatkill、重复退场幂等、retire后child失败整checkpoint回滚、battle字符串compile/数字runtime拒绝都实测。原177专门另3项通过：真实owner召唤child/lifetime5s，child已cast时owner3tick退场递归清理；windup/finish/lifetime任务取消且HP20/30保持、commands/CP/replay正确；递归cleanup后失败可完整回滚；control歧义self/source/selected早拒，明确all actor selector能退场无policy对象，不触battle。

## category真实反例与修订

原source AdvancedSelector._targetCategory=DEFAULT1是已知数学字段，原selector只有enemy/ground/alive造成真实漏接：missing category和explicit1应命中，explicit2/device应排除；实际原177命中3/4/5三目标，设备HP3000→2200。最小完整fixture/runtime/definition/commands/events/CP/replay保存在m15_emp_category_original177_peer.json，不降成只有native方法体未知。

新f98a核心加通用数据field filter；EMP79ed使用definition scope metadata.native_category、bits_any1、显式default1。新原反例同expected复验只命中3/4、设备HP3000。扩展mask矩阵中missing(default1)、1、混合3命中，2/4/0/True/string1/None排除，验证bool不等价整数类别。它没有角色ID特殊分支，也不靠额外tag偷换。

runtime vs definition真选择：runtime hp.current70，definition hp.initial80；definition缺current时用明示default91，runtime有current70不会用91。直接selector计算记录为API-only，它会发可观察calculation trace，因此不冒充command replay。int.real不是数据key，不进行getattr；nonJSON带副作用property对象编译拒绝且getter未触发。坏path、bool索引、equals/bits_any互斥、bool/负mask、非法scope、NaNdefault全部明确拒绝。

最初两个scope test因我新selector没由owned probe引用而被Compiler正确裁剪，表现KeyError；补显式probe引用后通过。该夹具错误旧初report保留，不是core缺陷，也没有修改EMP所选能力/selector迁就预期。

## 最终范围与身份

新f98/79ed coherent14顶层独立检查全部通过，其中incoming/payments内含5子场景，复用了原slice7与retire3的同一独立预期并fresh执行。另原category最小反例新input单独通过。新增empty cast也实际支付10DP/5SP，45tick只退场一次、HP100保持、无伤害，退场后请求拒绝。成功状态场景完整snapshot CP和recorded-command replay一致；失败直接API/schema/只读选择计算边界明确不声称命令回放。

Core、package、source和helper起止稳定。新generic classification不代替实际stage enemy category数据导入；原package旧client_pending类别文案保持历史，但DEFAULT mask数学消费者在新slice范围已闭合。Native finish callback时钟/category method bodies/2025 token对local2026仍client_pending。TrapMode/MapDependentTrap live tile buildability/pass/height/priority/cleanup仍model_gap，必须另实现和见证，不能由本14点升级完整EMP。

## 冻结文件

- `tools/experiments/m15_peer/verify.py`: `703d0b81072e00fe81e2737e5e142505fc66f24172a125586db91e7b1663c4e6`
- `tools/experiments/m15_peer/retire_boundaries.py`: `a8da3086f5d67a828e69e64b863b38fb4560d35541a152fa278aa36af53e9908`
- `tools/experiments/m15_peer/category_probe.py`: `9c27c6d8617fc6437b7c9f671be11cfb6c6daf015ef298b0dec28b42ae2025d4`
- `tools/experiments/m15_peer/category_matrix.py`: `2926165e3220fc28a8f470acce1a27a4521fbc7e26d861032d3715a3627ef82f`
- `validation/campaign/m15_emp_retire_peer_initial.json`: `616c81133155b3cde63ab620e5bc979ab5bb4ec8575370051d9779ccb04763be`
- `validation/campaign/m15_retire_boundaries_original177_peer.json`: `7007e26147b881349135c650bfb21ea594f292878ca34969b414db83c872f069`
- `validation/campaign/m15_emp_category_original177_peer.json`: `96f81e824d1ec087a7d4af433f88406055db8aca8f2f199dcdc350acbde343c6`
- `validation/campaign/m15_emp_category_f98_peer.json`: `5e068f1e161a88d4dd7bf8c2c973096c5b706f223d6f767bcba962814f4718d9`
- `validation/campaign/m15_category_matrix_f98_peer_final.json`: `db6535e36fb416cc57ba22ff889ffa364a3351913268bf0897be3b5a5b8de850`
