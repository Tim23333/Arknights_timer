# 原生卡片与自定义范围规则

当前正式主目录已推广到3992，下述卡片、自定义范围状态投影与运动同步接口均已进入主底座。
它自己的1219项完整回归、0-1/custom基线与36个不同独立用例通过后精确推广，
收据为 `validation/campaign/chapter07_final3992_primary/promotion.json`。后文保留各隔离版本的发现与验证范围，
这些底座结果不代表第七章整关已完成。

第七章原始 7-18 输入包含固定编队之外的 15 张地雷卡。
固定十二人仍是玩家选择的干员，不能用第十三个 roster 项替代原生装置卡片。
原公开部署接口仅允许 `scenario.roster` 中的定义，实际 fixed12＋地雷场景已证明这个缺口。
新的隔离候选增加 `scenario.cards`，将卡片部署授权与选中编队分开。

```json
{
  "roster": ["unit/custom/operator_a", "unit/custom/operator_b"],
  "cards": ["unit/custom/device"],
  "resources": {"device_stock": {"initial": 15, "capacity": 15}}
}
```

`cards` 是最多128个唯一实体 ID 的列表，与 roster 不重叠，进入正常依赖闭包。
卡片定义必须声明 `deployable.stock`，绑定实际存在的有限整数战斗资源。
部署仍使用相同的费用、库存、地形、占位、同时部署数、槽位与冷却验证；声明卡片不预先支付或补足资源。
缺失卡片声明时，原 roster 限制继续生效。
库存恢复和自定义成本仍由既有资源规则决定，原生关卡转换另核对卡片初始数量与所选技能配置。

当前 `campaign_scenario_cards_v1_candidate` 身份为
`478db2509508490f920fb08d24b3656cc995230d87eec31ab35a5ef19cd6d5c9`，父版本为4f16。
真实 fixed12＋地雷卡的公开部署、库存15→14、DP10→5、重复部署拒绝和磁盘恢复／重放已通过作者检查。
它自己的完整回归、基线和独立复核继续进行，正式主目录尚未推广这个接口。

## 自定义范围提供器的当前状态输入

源石和圆形范围已有固定提供器；第七章炮击需要原始连续3×3矩形。
自定义形状应保留自己的算法，不能借已有圆形或格偏移提供器的注册名来获得内部状态投影。
新隔离候选允许范围效果显式声明：

```json
{
  "op": "area",
  "membership_rule": "rule/custom/continuous_box",
  "selection_projection": {"defaults": "这里填写完整的类型化默认状态对象"}
}
```

上例的 defaults 字符串是说明占位，实际配置须是 `selection.DEFAULT_STATE` 结构的完整对象；
所有布尔、位掩码和异常状态枚举都经过严格校验。
该字段只适用于具有 membership_rule 的 area 效果。领域层准备当前 source 与候选目标的状态，
包括实际生效 Buff 的伪装、不可选取、冻结等贡献，作为 `context.area_selection_states` 交给纯范围提供器。

提供器仍负责自己的形状算法，并可以用 `context.calculate('targeting.eligibility', …)` 执行资格规则。
形状与阵营、运动类型、状态、主目标包含等规则分别声明；投影本身不决定哪些目标命中。
提供器只读快照，不读取世界或调度器。动态效果的非法投影也会明确拒绝，并回滚所属领域事务。

当前最终候选 `campaign_area_projection_v1_candidate` 身份为
`788f388ec892abca97c8d0cf6ca2329998768f273e66edef21bb000485492c8e`，包含前述卡片与4f16能力。
作者检查已实际证明连续矩形角落 `(1.5,1.5)` 命中、`(1.50001,0)` 排除，
中途真实伪装 Buff 改变资格，磁盘检查点与公开重放一致，以及类型错误拒绝和旧范围场景兼容。
它自己的完整回归、基线与独立复核正在进行；第七章原始炮击消费者另行绑定该接口。

独立反例随后发现公开 `set_motion_mode` 更新了物理模式而未同步目标资格 motion。
修订后的 `campaign_area_projection_v2_candidate`（3992）在同一事务中更新
`spatial.motion_mode` 的 WALK0／FLY1 与 `selection_state.motion` 的地面位1／飞行位2。
公开切换、动态范围投影、普通选取、飞行中命中和落地后的重新选取现在读取同一状态。
角色静态 tags 不会代替这个动态运动资格。
原失败用例以及初始CP0／CP6、原生卡片、波次和来源消费者交叉检查已在3992重新独立执行通过；
该版本自己的完整回归正在收口，旧788失败报告与原生草稿仍保持旧身份。
