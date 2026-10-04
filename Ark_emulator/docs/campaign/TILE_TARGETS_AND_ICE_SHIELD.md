# 地块目标与霜星冰封参考模块

当前开发按用户指定：数值与机制先从既有参考网站、固定公开数据、资源文件提取；客户端统一对照由用户在完成后反馈。游戏接口不是当前开发前置要求。

地块目标独立于单位目标。候选 `campaign_tile_targets_v7_candidate` 基于冻结 M94，核心身份 `42014647b8d510c6394b98221c138a0bc27a8ccab3354d653a65fc2767fb3833`。它尚待独立复核与霜星普通攻击／ArcticBlast 候选合并，不替换当前主目录，不迁移旧回放证明。

## 通用能力

- `ability.tile_selector` 声明纯资格表达式、参数、数量上限、排序／无放回均匀抽样方式与显式随机流。只读 `query` 不写事件、状态、任务或随机数；接受施法事务内才消费随机数并记录候选和选择结果。
- cast 将地块保存在 `tile_targets` 坐标列表中，保留于真实 World、检查点和回放；没有为每一格伪造单位 ID。
- `spawn_on_tiles` 从真实 cast 消费捕获地块，声明执行时是否重新核对地块资格，以及地块根位置上的单位过滤表达式。即时击杀调用现有 `InstantKill`，不会伪造巨大伤害包。
- `tile_occupancy` 用严格布尔值声明 `blocks_deployment`、`exclusive`、`targetable`、`withdrawable`。部署资格读取占位；无命中框 token 从普通选敌和效果目标中排除；禁止手动撤退实际在公开命令入口执行。
- 生成占位物不使用玩家卡片或 DP／库存支付。占位本身不更改原始地形、移动成本、地面可通行性。源单位退场后保留还是清除由所有权策略声明。

任一地块生成失败会回滚整个效果事务，包括此前地块的击杀、token、事件及任务。施法成本不够、资格表达式返回错误类型等失败也不消费随机数。隐藏、活跃、单位类别及具体 collider 语义需要相应内容表达式明确选择，地块根坐标模型不自动冒充原生接触体。

## IceShield 的来源与参考政策

生成入口 `tools/build_chapter04_ice_shield_module.py` 固定 `chapter04_boss_plan/source.reference.json` SHA `7ad2fb46b3e281711b6faf8b7a3bacfb9df6bc11ff32212a8439d8925d6893ec`。当前源模块为 `packages/campaign/chapter04_boss/ice_shield_v3/module.reference.json` SHA `490b35461d4ef1e53549a97312f061264f124defefa2a962a83b0e95fb9d1e4a`。

源数据提供初始冷却30秒、冷却30秒、优先级2、最多2格、Skill 动画帧55生成、`InstantKill._skipReborn=False`。冰块资源 `_rewriteTileOptions=0`；[封印的地面参考](https://prts.wiki/w/%E5%B0%81%E5%8D%B0%E7%9A%84%E5%9C%B0%E9%9D%A2)和[霜星参考](https://prts.wiki/w/%E9%9C%9C%E6%98%9F)保存在来源审计内。HP100取参考资料，公开角色表缺该 token 条目；2025 token 资产与固定公开表版本差异保留。

模块明确采用半径2内可部署格的中心距离、排除当前部署占位、接受施法时均匀无放回选择、帧55对该格当前 `player` 根位置单位执行即时击杀。冷却当前从施法完成后计算30秒。原生 `EXCEPT_CHARACTER` 过滤正文、几何边界、随机消费和技能冷却起点尚无直接算法证据，因此这些是可替换参考策略，不能标为已恢复原生实现。后续根据用户核对反馈修改内容表达式和政策并生成新版本证据。

源模块依赖另一候选的 `initial_cooldown_seconds`，尚未以组合内核编译／整关运行。旧 v1／v2 内容生成产物保留最初未编译身份；v3 为当前准备版本。

## 已执行验证

`validation/campaign/tile_targets_v1/author_tests_v7.json` 的7项真实执行测试 exit0，含公开施法与即时击杀、检查点续跑与从头回放、部署占位、源退场保留、禁止人工撤退、只读查询不消费随机数、失败成本／资格回滚、exclusive 生成原子性、执行时复验、跨格失败整体回滚、休眠 token 激活冲突。前期失败报告保留，原问题为夹具缺策略／DP及读取冻结对象方式，未用删断言冒充通过。

另已实际运行82项相关兼容测试，exit0／4.25秒，涵盖技能、所属单位部署、回放、场景效果、空间与预定义单位转换。十个修改源文件逐字节冻结，收据 `freeze_v7.json` SHA `bd199b58245cc0655ca342f7957ef592a4a67b10680bf678ff992261a63d631c`。

尚待独立反例复核、有效覆盖参数校验、与初始冷却及普通／Blast 合并，然后组装4-10的完整43次出生。当前没有4-10整关通过证明，客户端核对保持未执行。
