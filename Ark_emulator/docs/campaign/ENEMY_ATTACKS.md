# 0-10 原生敌方普攻转换

`tools/build_campaign_enemy_attacks.py` 扫描真实 `enm_pfb*.ab_unpacked/CAB-*`
并定位五种敌人的 GameObject、默认模式和 combat Mono。输出
`packages/campaign/enemies.00_10.attacks.json`，保留源文件 SHA、mode/combat
path ID、完整原始 combat 字段与 `mode._attack` 空引用。

这批 prefab 的普通攻击实际存储在 `mode._combat`，不能根据为空的
`mode._attack` 判定没有攻击，也不能从名字猜测伤害类型。
四种近战 combat 均明确 `_damageType=1`、`_atkScale=1`、`_animKey=Attack`。
模型使用冻结动画参考的 OnAttack 事件，伤害和攻击间隔读取来源明确的有效属性。
原生动画缩放、FSM及与客户端的逐帧校准仍独立标记 pending。

| 敌人 ID | 原生 ATK | 当前模型首命中 tick | 目标策略 |
|---|---:|---:|---|
| enemy_1007_slime | 130 | 10 | 当前阻挡者 |
| enemy_1027_mob | 250 | 12 | 当前阻挡者 |
| enemy_1030_wteeth | 500 | 19 | 当前阻挡者 |
| enemy_1000_gopro | 190 | 18 | 当前阻挡者 |
| enemy_1005_yokai | 0 | 无攻击 | 保留 applyWay=NONE 与 FLY |

`tests_v2/test_campaign_enemy_attacks.py` 对真实 Compiler/Engine 执行独立伤害
与时点预期，并核对同位置其他友方不受攻击、无阻挡时不自动找人攻击、
无人机即使存在 Spine Attack 事件也不生成攻击能力。
七项独立测试通过；`--check` 重新解包核对生成内容，拒绝来源漂移。

该包补充首关草稿的敌方攻击定义；正式关卡仍须加载完整十二人及原生控制，
并取得独立转换审查。它不提升主线通过数或客户端对照状态。
