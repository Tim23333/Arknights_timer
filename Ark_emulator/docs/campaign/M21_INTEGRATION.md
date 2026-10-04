# 第1章通用能力组合候选

M21 将冻结的M18地形/传送、M17持续投射物和M20来源隔离组合至新目录。当前候选
`D:/Arknights/Arknights_timer/unpack_work/campaign_m21_integration_candidate` 的core为
`c069e0206c076b429750b3fd97a507c54fb8e34fee51376c2f979f434151b95e`。未合入生产，未签整关收据。

构造工具在 `tools/candidates/m21/`：逐个核对父实现，按共同祖先三方合并，保留人工冲突记录。文本合并输入单独规范换行，旧源文件原字节不变。两处依赖注入冲突明确保留terrain和projectile两种系统及纯provider。所有初始未解冲突与最后70个源/catalog文件哈希记录在 `validation/campaign/m21_integration/`。

独立terrain审查发现旧M16/M18纯规则可以改tileKey、黑板和effects而没有执行相应机制。新组合只允许已支持的6个PATCH字段及groundPassable/movementCost改变；其它身份与行为metadata可省略继承或精确相等。新独立3项检查确认未知行为拒绝、合法partial数值保留身份、自定义成本7/高度.75有效、portal身份不能旁路替换。

首次组合 `079da0...` 的102个机制/兼容检查通过，但额外跨模块反例发现：C4附着于注册实例、该目标退场后，inactive门把存储点爆炸也挡住了。失败版本字节保存在 `unpack_work/campaign_m21_history/079da0...`。当前修订允许有明确center_position的area使用保存几何点，范围内成员仍按有效状态过滤；真实退场目标HP保持5000、邻居受746后剩4254，检查点与全部命令回放事件相等。初始失败与修后通过分别保留。

## 场景输入与验证范围

`tools/build_chapter01_integrated_models.py` 以冻结1-11休眠/1-12传送wrapper组合完整W投射模块，保留关卡属性、速度、路线、原始波次、控制、预定义和固定队伍。使用单独metadata-corrected W文件，描述实际C4 at_hit、实例寿命/invalid等待及数学fixed/follow模型，旧包和旧运行不重标新指纹。

| 输入 | 当前编译 | SHA |
|---|---|---|
| m21/level_main_01-11.partial.json |276 definitions|`2fd475a0491c86b0ab8d48ff1a17b983e5156d23bc5ea20a77782c8484e77e33`|
| m21/level_main_01-12.partial.json |273 definitions|`9aa6f6b6aceb2eb1f2ced0013025765742f305d2b31dbf045e6c13201424154d`|

早期079输入保存在同目录 `history_079/`，没有覆盖为当前core通过。所有partial仍保留敌方过滤/FSM、普通远程依赖、教学编队、完整关卡和新的组合复核缺口。

三个旧机制套件只替换candidateRoot字符串产生新的测试副本，断言逐字保持；复制证明在 `test_source_copies.json`。旧源码不修改，新执行锁定实际组合core。
当前core的0-1/custom三路验证已真实结束且identity guard exit0：11击杀、0漏怪、300刻检查点和完整命令回放181937事件一致，自定义850/60通过。
首次完整tests_v2+机制套件已实际结束：8 failed、1224 passed、1 skipped，1519.12秒，core开始/结束相同。
其中6项缺少候选离线JSON，补入后7项导入检查通过；另1项canonical Kalts使用旧M8默认包、1项仍断言catalog82而新terrain合同使其为83。
缺省未指定M10 isolated root还跳过了原独立资源检查。新的明确输入runner固定当前0fb内容与候选root，并将旧rules测试仅count82→83复制到新路径，原primary测试不改；受影响套件正在重验。

明确输入/样例路径修正后的完整复验已真实结束：**1236 passed in1534.70s**，exit0，core与源码/catalog/输入开始结束相等，没有skip。
旧1232项尝试的失败及原copy路径失败仍保留；新runner固定源包、isolated review root和83合同测试副本，样例读取仍指同一repo文件。
当前通过只归属于c069候选与本次完整选择，没有迁为M23/M24/M25或正式关卡收据。

全套早期出现6项0-1导入路径失败：候选目录缺少DEFAULT_PACK需要的离线JSON。已经按原字节补入唯一JSON，7项导入测试另跑通过，没有导入历史战斗Python。原全套失败仍保留，不能把补充通过重写为原全套全绿。
