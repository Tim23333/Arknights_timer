# 第十一章来源计划

固定56数据中，本轮标准目标为 `main_11-17`／`main_11-18`，展示为11-19／11-20。
新来源清单位于 `packages/campaign/chapter11_source_prepare/source.plan.v1.json`，
SHA为db510b260c64266315fd22ea2a5f2708434089d4be4272e9afb4c7dc148c6518。
它完整保留原LevelDataJSON、StageTable行、敌库原引用及override，未创建模拟。

两关共9个敌人变体。11-19原10次出生／14条路线，11-20原35次出生／27条路线；
原DP分别3／10、部署槽均8、基地生命分别1／3，未来只覆盖基地生命为99999。
地图、路线、原等候、传送、runes、branches、globalBuffs和预置对象均逐字段保留。

11-19是标准main目标内的原生教学关：isTrainingLevel=true，预置4角色／3装置／1装置卡，
包含4个STORY、2个ACTIVATE_PREDEFINED与1个PLAY_BGM控制。
固定12人只是选定测试负载，不能删NPC、提高原槽位／DP或移除控制来容纳队伍。
后续必须独立转换原角色实际配置、装置、激活注册、输入／时钟策略及真实占槽，
把固定编队选入、玩家实际部署与NPC行为分别记账。
11-20为原生普通关，含8个DISAPPEAR与8个APPEAR_AT_POS及1个敌情显示动作，
原装置卡也需完整来源及生命周期。

敌人包括蒸汽骑士S、枯朽战士／组长、逐腐兽、腐败之种、枯朽战车、
城防自行炮／高准度版本与“最后的蒸汽骑士”。
已解析敌库skills／blackboard并完整保留，但这不证明运行能力已实现：
仍需确切prefab、拥有组件、动作帧、弹丸、BSON、阶段切换和被动声明闭包。
炮的Cannon与战车PollutedRangedAtk及HeroBomb各状态必须分开消费原参数，
不能借第十章炮控或Boss模块替代同名相似机制。

来源闭包复核还发现11-20的四个原分支route1–4，每个都包含真实SPAWN
`enemy_1266_nhapos`，该key不在本关enemyDbRefs的9变体清单中。
原branches已完整保存在计划，35只表示原主波次出生，不能把分支额外出生丢掉或改回35。
后续应单独提取其精确prefab、固定DB原层与分支触发来源，明确原生等级／override如何选定；
没有来源时不得默认level0。还需确认分支的路线索引与extraRoutes映射、实际触发次数、
受管理成员和终局／检查点出生账，不能只靠enemyDbRefs关闭依赖。

新 `tools/chapter_source_inventory_v1/build.py` 也支持后续12–17章的同一固定来源盘点。
它锁定StageTable字节、原目录及敌库，按NORMAL与原生序列核对该章最后两关，
保留全原文件并确认加载后逐字段相等，不依赖旧零坐标投影。
这仅为后续开发准备，正式通过数不因数据清单增加。
