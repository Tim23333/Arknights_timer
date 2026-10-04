# 霜星完整参考消费者与通用技能裁决

当前主目录为经过完整测试、基线与独立复核的组合 v5，核心身份 `7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90`，catalog SHA `679ae41d4276865e1100fee6969d2ab1cb0ea913d50f63bc04a04dbf23b9f246`。2026-10-04 已逐字节推广89个py/json文件，完整suite1219项通过，主目录与冻结候选三program/runtime重建身份相同；旧M68完整备份和旧收据身份保留。下文 v4／v8 等描述为历史实施与反例记录。

## 可配置技能裁决

实体通过 `ability_arbitration` 指定全部参与技能、整数优先级、优先级方向、是否使用攻击时钟、是否要求攻击控制、条件表达式和参数。`busy` 可声明全部施法占用或仅阻塞施法占用；相同优先级使用声明条目顺序。高优先级能力暂时因资源不足、目标不合法或冷却不可用而拒绝时，先回滚其状态、随机与任务，再尝试下一条；内容错误继续抛出，不伪装为合法回退。

技能的数值时间仍调用可替换 `time.interval` 与 `time.quantize`。实例覆盖在编译及分配前校验，休眠实例也不接受未持有能力。无裁决配置的单位保留原调度行为。

裁决 v3 的16项作者测试、9项独立反例及106项相关兼容测试实际通过。最初对 started 回调要求攻击时钟清零的测试期待错误：本底层以同刻 `event_reaction` 在接受施法后执行，因此接受的时钟30先提交、随后退场取消施法任务，已接受时钟不应被抹除。原失败报告保留，正确事件次序已由独立复核与回放证明；该错误不冒充内核漏洞。

## 地块修正版

独立复核证实旧地块 v7 三项漏洞：limit0仍接受／扣费、伪造cast可生成token、已完成cast可借新坐标执行。旧报告 `tile_targets_v7_independent_peer/verification.json` SHA `382f92c3c5b78435df7927b04fb936a0185da382461c0175c13c3a73630e9c19` 原样保存。

新 v8 在付款前检查有效数量，且从实际当前 World cast 校验 source、ability、generation、捕获坐标后执行。八项作者测试及原十项独立断言真实通过，后续新独立反例仍在进行。旧v7只保历史身份，不能作为已修复版本验收。

## 霜星三技能消费

组合内容 `packages/campaign/chapter04_boss/frost_complete_v1/module.reference.json` SHA `1e452d2a260af4590fa4a4aa0ef3eb2a8298f8ca332753af36b657b192e6fa6c`；生成入口 `tools/build_chapter04_frost_complete_module.py` 固定普通／Blast来源 `8ba0c574...` 与 IceShield来源 `490b3546...`。实际 Compiler 已通过引用闭包。

保留HP25000／ATK420／DEF250／RES50、第一次血量0后休眠5秒并恢复全血和ATK630，第二次真实死亡；普通首事件帧17、Blast帧28及技能范围／减攻速政策沿现有来源模块。Ice初始30秒、CD30秒、帧55创建最多2格token、真正InstantKill允许复活、token占位／不改地形／不可选中／不可人工撤退。

三技能优先级当前明示为Ice2、Blast1、Normal0，全施法占用抑制后续施法和移动。全部使用普通3.7秒攻击时钟属于参考策略，Ice资源的castLikeAttack0不足以证明原生仲裁门，保持政策可替换。Ice技能持续当前取事件帧55，恢复后重置30秒；原生动画完成时间、暂停／重置细节、选格filter／随机／几何正文仍明确未核实。参考来源优先完成仿真，后续由用户统一客户端反馈修订。

`behavior.decision` 增加可选纯数据 `tile_candidates`，让行为规则判断地块资格与全部施法占用。查询不消耗随机数；真实接受施法才抽样。

## 实际组合证据与待办

三项真实组合测试通过：初始覆盖0时Ice优先于Blast／Normal，帧55真实创建2token、下一攻击时钟111释放Blast；实际默认初始clock900／255、随后三技能触发；NoSource伤害于20打倒真实霜星、170同实例恢复，Ice1070／Blast425重新就绪且未发生已取消的冰封生成。真实检查点与从头回放均一致，报告 `complete_initial.json` SHA `693c1fb9e395ee08dc5eec2ceb737bf08d24e08cf9393a25d4af31f020877bbe`。

当前组合 v4 140项受影响模块／来源测试实际通过65.73秒，报告 `components_v4.json` SHA `af7149308fb5ffb26184f9ea00fbee56e8076fadf0977d2abee2b83693632c2b`。独立组合审查、标准0-1／自定义基线及完整4-10尚待执行。4-10必须保存43次出生、7精确变体、原部署上限10、DP10／99、移动倍率0.5和原传送路线；仅基地生命值覆盖99999。

## 后续独立反例与组合 v5

进一步复核保留了v8的新失败：活cast的传入ability不一致未拒绝、Bool generation等于整数1、目标真正进入rebirth.on_begin同步控制回调后源cast中断仍继续生成token。独立报告 `tile_targets_v8_independent_peer_v2/verification.json` SHA `a0e1048ed1f92551281060088447b5f8e90e0299839bb15f0938b2405cb4db4c`。on_remove回调在两token与finish后才执行的早期错误期待另存，未把真实事件顺序误判为漏洞。

tile v10 core `2eeca1dc0a9a02f2ba42aed2285d0ea89062029de8e2c58506c30e41472462cb` 采用严格source／ability／generation身份，并在每格、每次击杀前后复核当前施法租约。同步回调中断后保留已经发生的InstantKill／目标复活，停止后续token生成。八项作者及原十项、六项新独立反例全部通过，16项复核重跑收据 SHA `6be8cb2c4de8b8f86f256a9632f4d0845ca0c16d3056e0398a4f0fdc59afd68d`。

最新组合 v5 为 `campaign_frost_complete_v5_candidate` core `7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90`，catalog仍 `679ae41d...`、霜星来源模块仍 `1e452d2a...`。它只替换v4地块实现文件，不覆盖原v4通过或失败身份；三技能受控证据在新版本再次执行中，独立组合审查和4-10短前缀组装继续。

36关目标不缩小，正式计数在收据齐备前仍1/36。客户端验证保持未执行，当前目标开发依照用户指定资料来源继续。
