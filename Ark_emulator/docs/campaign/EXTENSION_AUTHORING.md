# 主线驱动的通用扩展入口

当前开发基于独立V2；新机制在候选中先验收，再提升主目录。主目录仍冻结bd60，下面M47扩展需要明确选用`campaign_m47_chapter02_reentry_integrated_candidate`或随后审查通过的版本。JSON例子仅描述入口，完整fixture和真实执行证据位于对应报告，不承诺未运行配置自动准确。

## 只改变伤害请求的一项数值

M43新增纯provider`model.damage.request_field_transform`，规则作者指定字段名、乘数与缺字段默认。它复制完整request，再改变指定数值；不依赖ATK/DEF/RES必然存在，适合自定义伤害管线及扩展参数。

```json
{
  "id": "rule/custom_outgoing_scale",
  "kind": "rule",
  "contract": "damage.request",
  "implementation": {"type": "provider", "provider": "model.damage.request_field_transform"},
  "parameters": {"field": "scale", "factor": 1.7, "default": 1}
}
```

Buff的before damage hook引用该rule，并写显式条件与优先级。后续`damage.pipeline`是否消费scale由其契约决定：温蒂距离规则只读取distance/value/per_distance，所以本变换保字段但不会擅自改变其公式。要改变该算法，作者替换对应pipeline；实现不能删扩展字段来适配预设公式。

## 地形占格光环与环境接触

`map.tile_mechanics`按任意tile key绑定机制profile，不凭官方地形名称选算法。`occupancy_buff_field`必须提供静态field entity与全部`expected_blackboard`，每cell形成独立来源，通过正常Aura selector/member Buff变更数值；成员离格及来源失效走同步清理。虚拟field不能进入战斗选目标、伪装普通actor或注入行为/技能。

`contact_lifecycle`必须提供纯`tile.contact`规则、普通路径／强制位移／显现通行选择、HP处理、死亡原因及是否逐tick复判。规则读取entity/tile/cause/motion/ready/parameters，返回严格bool。出生保护由Buff的`contact_flags.defer_fall`显式提供；不能从stun或不可选中状态猜环境免疫。普通路线与强制接触独立配置，墙与地图边界仍裁剪。完整profile见`packages/campaign/chapter02_tiles/m41.hole.profile.json`，其source/参考/数学选择和待用户核对項分列。

## 场景模块与精确依赖

`tools/campaign_content_composition.py`合模块并通过当前选定Compiler收集实际可达定义。相同重复定义允许；冲突必须显式完整replacement、reason和source。裁剪后重新编译比较完整可执行定义，不能按文件名或ID含probe就删除。十二人module、五敌module、地形module与关卡时间线各自保存来源锁，最终关卡只包含真实引用闭包。

字段分为源数值、声明默认和运行状态。`spatial.motion_mode`用于移动，不自动生成伤害hook读取的`selection_state.motion`；native运动枚举WALK0/FLY1与选择掩码WALK1/FLY2也不能混用。关卡组装器须明确映射，初轮airdrp失败正是这类缺消费者。输入审计可以发现必需typed motion，但不能审批所有规则语义。

M46正在添加通用纯`area.members`，精确九宫格等范围可由作者offsets或自定义规则决定；现有radius路径不变。该接口仍待冻结／独立复核，不能在主目录宣称已正式支持。

M46/M48该面积接口现已有25作者、18独立及1367全量候选回归／首关基线，范围规则可替换。主目录仍旧身份，使用候选要明确runtime-root与源码SHA。新M51库存接口为`deployable.stock {resource,amount,rule}`，同public/owned部署实际成功扣battle库存，rule是resource.cost，可改支付数量；compile要求库存存在。公开DP结算实际delta不足计划费用时原子拒绝，World deployment_recorded防重复记账。79检查和完整首关基线通过，peer／合M49后的新身份回归仍继续，不靠字段存在证明完整障碍卡片。

源枚举直接决定内容标签/掩码：EntityCategory DEFAULT1、TRAP_OR_ITEM2、OBSTACLE4；crate的真实根类别4不能改2迁就敌selector。AbnormalFlag INVISIBLE9与CAMOUFLAGE17独立；免疫/揭露是live投影抑制源flag，不删除原Buff。新M49 toggle/availability为声明profile开发，sourcecheck/restore3s/attackevent/blocked持续hold和sensor25cell/15SP/20s分列验证；当前开发不能在旧primary默写未知字段。
