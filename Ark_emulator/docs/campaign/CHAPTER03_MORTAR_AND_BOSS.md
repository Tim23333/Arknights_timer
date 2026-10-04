# 第三章 Mortar 与碎骨 Level 1 内容

两份新内容均从冻结 `chapter03_sources/native.reference.json`（SHA `d6a1d5294e1419d6ee41022efa1ef93a0ad44b6effb80c4bdfcf7fc3e7cd1e35`）按 exact native variant 读取，不替换旧关卡、Boss或任何候选源码。表源固定于公开数据 commit `56aee3d6c5a29c3a0d192456d70d14252cbb0804`；全部 raw prefab/PPtr、Spine与源字段仍在冻结源包及其 source locks 内。

`tools/build_chapter03_mortar.py` 生成 `packages/campaign/chapter03_models/mortar.reference.json`。实际 VID 为 `enemy_1024_mortar@0/6408b1bf3f6a0758`，HP 3300、ATK 400、DEF 150、RES 0、间隔 4.5 秒、射程 7。UnitMode 的 `_combat` 与 `_attack` 指向同一 RangedAttack，`_selectTargetSource=1`（FROM_OWNER），不套用 INPUT_TARGET=2 的强制 blocker 优先。Spine Attack 唯一 OnAttack 是精确 authored frame 16，Builder 读取并断言它。源 SimpleProjectile lifetime 10、INFINITY=2；inactive maxHitNum=1 不作为额度。Paracurve speed 4、raise 1.5、height threshold 1.2999999523162842，HitBehaviour 的 targetOptions side2/motion3/category1、ignoreTargetFree0、ignoreCamouflage1、goThroughWall1、onlyCheckHitWhenReach1 全部保留。

2026-10-03 实际读取 [PRTS 炮手](https://prts.wiki/w/%E7%82%AE%E6%89%8B)：普通攻击选择地面目标，炮弹影响目标格及周围八格，溅射能够命中飞行单位并忽略迷彩。声明模型以 M53 的 pure qualified area 真实消费该资格，而非只用 player tag；地面主目标与空地溅射分离。弹道采用可替换 planar homing，落点为捕获目标当前可见位置；无效或 route-hidden 后保留最后观察位置，源退出保留已发射包。原生三维 paracurve、父变换、命中和到期回调正文未恢复，这些明确是数学政策，不称原生算法已验证。

攻击在 frame16 发射，未移动目标距离4格，于 tick46 结算 physical 400−DEF50=350。公开命令 tick30 移动目标到下一格，同时另一实体给源 ATK+100，真实 tick54 结算450，证明捕获目标 ID 未换且属性在命中时读取。目标退出或 route-hidden 时，主目标不结算，最后点附近合法飞行邻居仍结算350。短寿命到期分支只派发一次 blast，不重复 reach/expiry。原始同旗标但 native 特殊 callback 与排序仍保留反馈项。M53 standalone 未绑定 INVISIBLE9 availability；后续 M54 合并应逐场景验证，迷彩17许可不能绕过9、target-free或类别门。

`tools/build_chapter03_boss.py` 生成 namespace 独立 `skulsr.level1.reference.json`（SHA `c09cc02578055091f1ae465954ecfa484a6cafe21ab5b5b84f3c2deab8380092`）。实际 VID `enemy_1500_skulsr@1/6fab9b304b7efcba` 的 HP30000、ATK1300、DEF240、RES30；源 BB hp_ratio=.5、atk=.5，因此标准初始阈值15000、低血 ATK1950。阈值读取有效 HP capacity×.5，不复制旧关5250，也不硬编码15000；有效上限变化同样重新判断。HP0 不进入阶段循环。复用冻结 reference50 的显式 packet/impact/DEF减益策略，source prefab .4 与表/参考 .5 的冲突仍原样保留，客户端 loader/FSM单列反馈。

Boss 在 M48 a829 实际7项测试通过3.64秒，含等于15000不进入、14999进入、恢复、maxHP40000、有效容量改变、HP0、两发精确源帧及 ATK1950、生命周期漏怪实体数1但扣基地2。报告 `validation/campaign/chapter03_boss/final_review.json` SHA `10692b895aa4e4e54e50fbacdba4b65d50d8a5531a06c0ad22519478b8f0f4f0`，两组公开输入都完成 ordered CP 与 commands replay。

Mortar 在 M53 5ed2 独立13项测试与三组公开输入执行，实际报告位于 `validation/campaign/chapter03_mortar/final_review.json`，包含每次编译输入、命令、ordered CP、回放、最终快照与起止源码身份。Builder `--check` 实际验证产物字节。所有测试是短模型，不是整关完成；client_verified 与 formal_approved 均 False。最初缺显式 attach_at_launch 与 target retain_position 类型是内容作者编译失败，日志保留，修正后才计实际运行成功。
