# 技能组合与首关内容草稿进展

当前持续目标仍为固定十二人、36个标准主线尾关；本阶段完成了更多源支持组合原型和必要通用执行契约。
源支持原型、完整干员、正式主线和客户端校准分别记录，不把合成场景的通过提升为关卡验收。

## 新通用契约

- `activation.on_start`：支付后在同一原子启动内同步执行效果，建立模式/Buff后再让同tick普通攻击采样；失败回滚支付、状态、任务和事件。
- `activation.parameters.auto_only`：仅自动系统可启动；满SP玩家命令仍明确拒绝，不改变模式和资源。
- `buff.control`：move、attack、abilities、block布尔限制在活动实例上合并，采用半开有效期；interrupt显式指定时取消已开始的施放。已发射弹道按其已排队生命周期继续处理。
- 伤害分配：独立shield charge资源支出不再计作HP伤害；混合分配只用实际目标结算资源损失统计damage.accepted和damage_dealt。
- 编译器同时检查timeline与on_start的source/self资源引用，缺少资源在执行前拒绝。

## 已运行原型

| 原型 | 当前实际执行 | 仍未完成 |
|---|---|---|
| 桃金娘S2 | 费用、周期治疗、停攻/零阻挡、SP冻结与恢复 | 完整官方单位/天赋/动作及16秒同刻客户端排序 |
| 能天使S3 | 自动满SP同步切模式、动态5连射、1.1物理倍率、原生发射间隔与弹道、到期恢复 | 全单位/天赋与客户端动画/FSM对齐 |
| 陈S1 | 普通双击每cast一次SP、4SP自动下次攻击替换、3.2物理倍率、1.5秒真实控制与中断 | 全单位/天赋，prefab与Spine时序差异校准 |
| 雷蛇S1 | 受击18SP自动支付、单次挡伤、8秒DEF与到期清理 | 全单位/随机邻友SP，incoming guard绑定及原生挡伤触发细节 |
| 白面鸮S2 | 首个mode1治疗packet、最多三名受伤存活友军、付款与40秒占用 | 治疗间隔渐变、持续治疗、普通模式恢复与全场SP光环 |

五份包均保持partial、synthetic fixture和client=false；白面仅first-packet，完整请求明确拒绝。
攻击线19项、支持10项和独立控制复核15项含真实付款、首tick、控制、尸体过滤、源过滤与检查点/回放见证。
细节见 [攻击组合](ATTACK_RECIPES.md)、[支持组合](SUPPORT_RECIPES.md) 和 [独立复核](ACTIVATION_REVIEW.md)。

## 首关草稿

`tools/extract_campaign_attacks.py` 已封存十二人的真实base mode0攻击/战斗/trigger Mono链、sourcehash与动画证据，
输出 [attacks.reference.json](../../packages/campaign/attacks.reference.json)，仍为source-only。

`tools/build_mainline_draft.py` 将0-10真实9×13地图、五种敌人、35个出生与路线转换到V2 IR，
显式保持地图top-down与原生路线bottom-up的坐标转换、费用/生命/部署上限和移动倍率。
[草稿](../../packages/campaign/mainline_drafts/level_main_00-10.json) 仍含真实未完成依赖：固定队伍、敌方普攻与原生控制，编译器拒绝缺失，
没有空处理器或普通技能placeholder；未成为正式`packages/mainline`内容，也没有提升36关通过数。

## 当前回归与下一批

583项全V2测试通过；新运行身份下0-1仍11击杀零漏怪，连续、检查点与回放的181,638条事件精确一致。
证据：[测试](../../validation/campaign/m3_primitives_tests_20261002.json)、[模型](../../validation/campaign/m3_primitives_baseline_20261002.json)。

后续继续其余七个所选技能、十二人完整普攻/天赋、动态光环、召唤及控制转换，并把这些真实依赖接入首关草稿，
再取得独立转换审查与正式模型结果。整体目标保持active，正式验收仍0/36。
