# 部署冷却、原路线保护与障碍物内容

当前候选根 `../unpack_work/campaign_m68_deployment_integrated_candidate`，核心SHA为 `1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8`。它组合冻结M63部署冷却与M69连通性修订；共同父为M58。重叠的schemas、compiler、deployment、lifecycle逐个明确合并，构造工具先在内存完成全部唯一锚点验证，再创建新候选。所有旧源码、失败与已跑报告保留。

## 内容接口

| 配置 | 实际消费 |
|---|---|
| `deployable.cooldown_start` | `deploy`从成功部署计时，`retire`从真实退场计时；省略维持旧退场策略 |
| `deployable.cooldown_seconds`及`deploy.cooldown` | 显式秒数与可替换纯规则；非法类型、负数拒绝，零允许 |
| `deployable.rules["deploy.cost"]` | 费用算法可替换，障碍物使用每张固定基础费用5，独立于干员重复费用 |
| `deployable.connectivity {rule, parameters}` | 显式纯`deploy.connectivity`决策；缺省无此能力，显式null拒绝 |
| `scenario.parameters.deployment_routes` | 唯一ID的完整原地面路线起终格，未出生路线也检查；编译时要求显式绑定 |
| `terrain.tile_options` | 实际寻路继续使用可替换代价；障碍物参考profile使用1000，保原通行mask |

标准纯提供器 `model.deploy.ground_connectivity` 接收有效地形／walkable快照、原路线、当前障碍格、新候选格及参数，临时把障碍格当作封口检查所有原起终点连通性，不改World或实际通行mask。`diagonal`及`allow_corner_cut`必须明确布尔值；可替换提供器、表达式或图，严格返回accepted/reason。不会仅检查当前活敌或选出的当前移动路径。

公开与owned部署共用prepare／record。prepare在支付前验证，record读取创建回调后的真实位置、实际组件和实际actor快照。带profile的普通创建及休眠预置激活也在原子事务内前后检查，避免通过spawn或activate_predefined绕过约束。无部署语义的创建不隐含扣DP或卡片；明确强制创建政策可按`ctx.placement_phase`选择`create/created/activate/activated`，公共`prepare/record`仍独立受规则约束。

创建位移按现有half-up格投影，在候选检查中使用实际格。初始／波次实例参数先与定义有效merge，再检查profile与完整规则合同。扫描其他障碍物不会替换拟部署actor快照。嵌套record计算前预留World标记，整个支付、库存、创建、地形及规则失败仍原子回滚。

## 实际验证与失败保留

M63有26项定向及48项兼容，七个公开场景磁盘续跑／回放；无opt-in父／新263事件全值一致，仅准确列出的身份字段不同。M64初版实际暴露有效merge／null错误，M65又暴露source快照变量覆盖和休眠激活旁路，M66／M67逐项修订。独立反例完整保存在 `validation/campaign/m64_roster_peer`、`m65_roster_peer`；不把夹具或后续通过迁到旧身份。

M69补了无deployable组件的合法旧公开部署回归：默认空组件不能使新检查逃出TypeError。最终30项作者检查、84项实际旧部署／空间／激活／engine兼容通过。无opt-in父M58／M69各67事件，全值比对只存在108个明确根／calculation registry身份路径；所有原值、差异双方值和完整检查点／回放存储，没有按键名泛删payload。

M68实际组合385项通过177.47秒，完整0-1基线11／0、181937事件、磁盘检查点续跑、开局命令回放和自定义850／60公式通过。全套回归正在执行。交叉公开场景验证tick149冷却拒、150最后封口拒、151撤退释放、152重新部署成功ready302／库存3；完整事件／磁盘续跑／回放一致。另API回调scope独立确认nested record不能重复扣卡，不冒称其具有公开命令回放证据。

## 3-7实际接线

新crate内容为 `packages/campaign/chapter03_traps/crate.reference_v3.model.json`，SHA `5a084db4d7d675867d8febf563b5e6e442c31422c5a184185fff5f5bcddbc8f9`。保原HP100、category4、阻挡半径、五张卡片及地形数据；绑定恒费5、DEFAULT部署后5秒冷却、advanced mask1、寻路代价1000和原路线保护。原始`_cardPolicy=0`、`_ignoreBlockAnyRoutes=0`与参考规定分列。[障碍物参考](https://prts.wiki/w/%E9%9A%9C%E7%A2%8D%E7%89%A9)。

3-7源包SHA `147f9d619b2bc3a50adb630b74bdb713f825d16aa64d604ffc24d366510e26d6`，257可达定义、61出生、9变体、5控制。全部42原route中40条WALK用于部署保护；两个E_NUM预览路径保留于控制数据，未伪装地面路线。原Sensor位置／UP／HP／SP和五卡绑定保留。90tick短测实际1873事件确认费用5／库存4／ready150／代价1000，并完成有序磁盘检查点与回放。

基地生命值包SHA `7dbbe2270f6250927ca183cb99a8959fcc4e5160f3e3f9b5124dc887653aa817`，只改life初值／容量。58公开操作保持原文件身份 `e7a6453158cb57159e533c387dc58c58c8bf3f617d8031ab88d12c01edb1d7c7`；接受／拒绝由实际规则记录。新全程输出 `validation/campaign/runthrough/03_07_m68_full_20261003.json`，未终局前不计完成。旧M58全程因内容缺消费，在保输入、177MB有序检查点与进度后明确停止actualexit1，不作为新版正确性证明。

以上证明声明源／参考规则的执行与确定性。导航corner、圆／格映射和历史资产版本差异仍是显式可替换政策；用户实机反馈后另行核对，不将客户端未验证等同已验证。
