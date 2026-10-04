# 战斗模拟器参考资料

本文整理用户提供的工具链接截图，说明各来源适合解决的数据与机制问题，供 `Ark_emulator` 的数据提取、实现和验证使用。链接已于 2026-10-01 核对；访问结果只表示本次能否取得页面，不表示其数据一定完整或与本地客户端版本一致。

当前模拟完整性与代码问题见 [完整模拟差距评估](SIMULATION_COMPLETENESS_REVIEW.md)。

2026-10-03 用户指定：当前先使用这些参考来源完成仿真，完成后由用户统一实机核对反馈。来源缺方法体／当前无客户端接口不单独阻断声明规则下的开发交付；规则必须完整执行、来源与假设明确、独立测试可复核。当前访问与关键规则核对见 [参考优先交付](campaign/REFERENCE_FIRST_DELIVERY.md)。

## 图片中的八个链接

1. **网页版 AssetStudio**：[as.arkntools.app](https://as.arkntools.app/)
   - 截图原文为主机名 `as.arkntools.app`，这里补全 HTTPS。
   - 用途：作为资源查看与解包工具入口，辅助查找 Prefab、组件、动画和资源引用。
   - 本次核对：取得页面标题 `AssetStudio Web`；未测试上传、解包或导出功能。

2. **部分美术资源的解包路径**：[腾讯文档](https://docs.qq.com/doc/DYUhjZGZveWtpcXhT)
   - 用途：按截图说明，作为查找部分美术资源路径的备忘。
   - 本次核对：已从截图转录链接；抓取工具未能取得正文，文档内容、权限与当前有效性待核实。

3. **Buff 阅读辅助工具**：[TeamTorappu/BenaProtractor](https://github.com/TeamTorappu/BenaProtractor)
   - 用途：辅助阅读 Buff 节点、机制与黑板。可用于比对本项目 `buff_templates.py` 的节点解释。
   - 本次核对：项目首页与 README 可读取。README 提醒显示数值可能是默认值，具体值受黑板影响，节点翻译仍需完善。
   - 使用限制：工具的翻译结果应结合实际 Prefab、运行时黑板和战斗记录核对，不能单独作为行为已正确复现的证据。

4. **游戏数据仓库一**：[Kengxxiao/ArknightsGameData](https://github.com/Kengxxiao/ArknightsGameData)
   - 用途：核对游戏表与关卡输入，尤其是干员、技能、敌人、范围和关卡配置。
   - 本次核对：项目首页与 README 可读取；页面包含 `zh_CN` 目录，并说明部分数据通过 OpenArknightsFBS 解析。
   - 说明：使用已核对的仓库名 `ArknightsGameData`。

5. **游戏数据仓库二**：[yuanyan3060/ArknightsGameResource](https://github.com/yuanyan3060/ArknightsGameResource)
   - 用途：参考客户端素材、`gamedata`、地图、敌人、头像与技能图标；适合核对资源引用和展示素材。
   - 本次核对：项目首页与 README 可读取；README 列出素材类别，并提供 `version` 文件说明。
   - 使用限制：素材齐全不代表战斗算法齐全；图片和技能图标不能替代能力组件与脚本逻辑。

6. **游戏数据仓库三，含外服数据**：[ArknightsAssets/ArknightsGamedata](https://github.com/ArknightsAssets/ArknightsGamedata)
   - 用途：参考不同服务器的数据目录与自动抓取流程，用于版本比较和缺失数据检查。
   - 本次核对：项目首页与 README 可读取；仓库可见 `bili`、`cn`、`en`、`jp`、`kr`、`tw` 目录，README 说明使用 arkprts 与 GitHub Actions 下载数据。
   - 使用限制：不同服务器的数据版本需要分别固定，不能直接混合成一场战斗的输入。

7. **Torappu，往期包体数据**：[截图入口](https://torappu.prts.wiki/w/)，[根首页](https://torappu.prts.wiki/)
   - 用途：按截图说明，作为往期包体数据的参考入口；历史包体适合追查版本变化。
   - 本次核对：截图入口未取得正文；根首页标题为 `Arknights Asset Storage`，要求 JavaScript。未核实站内具体文件与版本。

8. **Weedy，部分游戏内数据抓包**：[weedy.prts.wiki](https://weedy.prts.wiki/)
   - 用途：按截图说明，参考部分游戏内数据抓包，作为静态配置以外的补充线索。
   - 本次核对：两次抓取超时，未取得正文。不能据此判断网站已经失效，也不能确认抓包内容覆盖逐帧战斗状态。

## 在项目中的使用顺序

先固定目标服务器、表／关卡提交、已提取资产版本和来源，再同步静态表与关卡数据。之后按实际引用补齐 Prefab、Buff、环境系统和动画事件，用独立场景核对参考数值与完整执行。用户在当前仿真交付后统一实机反馈，随后把差异映射到具体可替换规则。

| 要解决的问题 | 优先参考 | 本项目对应位置 |
|---|---|---|
| 干员等级、精英化、技能、模组与信赖属性 | 游戏表、客户端配置 | 离线`ark_parser/character`；V2 `packages/campaign/roster`、单位／技能内容与`ark_sim/domains/attributes.py` |
| 敌人等级与关卡专属覆盖 | 敌人表、关卡 `enemyDbRefs` | `packages/campaign/*_sources`及精确variant绑定；V2实体、规则与Buff内容 |
| 普攻与技能伤害类型、弹道、生效时机 | Ability 与 Projectile 组件、Spine 事件 | V2 `domains/abilities.py`、`effects.py`、`projectiles.py`与source-bound内容 |
| Buff 条件、目标、优先级与黑板变量 | Prefab 与模板原文，BenaProtractor 辅助解释 | V2 `domains/buffs.py`、选择资格及纯damage request/pipeline规则；原始Buff模板作为离线数据 |
| 地形、预部署、教程与环境管理器 | 完整关卡、环境系统资源、历史包体 | V2 `domains/timeline.py`、`controls.py`、`lifecycle.py`、通用terrain/tile profiles与场景数据 |
| 随机数与帧级行为是否一致 | 真实战斗记录；抓包资料须先核实字段 | `tools/ak_live_rng`，`tools/deploy_tracker`，`tools/enemy_health` |

外部仓库中的数据文件、网页说明和工具输出是参考材料。实现应记录来源与版本，并区分“静态数据确认”“源码或组件推断”“运行时实测”和“近似实现”。

`ark_emulator`内旧loader/battle/skills等属于V1历史参考，仅离线读取数据；当前运行、公式扩展和验收均消费独立V2 `ark_sim`。候选的源码身份与输入必须绑定，旧运行不自动迁成新版本通过。

## 建议保存的数据来源信息

每次重新生成模拟数据时，建议保存一份清单，包含服务器、游戏版本、基础包与热更包版本、上游仓库提交、文件摘要、提取脚本版本、生成时间，以及关卡、角色和能力条目数。缺失的战斗必需文件应在启动或构建检查时明确列出。

这些信息用于解释一项测试失败究竟来自实现、版本变化、输入缺失还是测试场景失效。网页能够访问和测试能够运行，都不能替代这份版本记录。
