# 第1章教学编队与公开部署边界

原始1-11包含12张教学干员卡，与固定12人配置不同。本批明确分开原生卡片的部署控制场景和主线固定12人测试覆盖，保留原始卡片、预定义、控制与限制来源。

## 公开部署约束

独立反例确认c069的公开deploy可以创建已经加载、却不在 `scenario.roster` 中的休眠预定义单位，也接受显式空roster的部署。第一次测试把该单位放为活跃实例，先被已有already_deployed门挡住，属于fixture错误；调整为真实休眠实例后才复现两项成员边界失败，两个报告均保留。

新候选 `unpack_work/campaign_m23_roster_candidate` core
`0258f171d31daffb7b917e2ebad2603505e5fa762e99ef4a71b3b30342d62381` 只增加公开 `_deploy` 的成员检查：显式roster只允许列表中的definition，显式空列表拒绝所有公开部署。省略roster保留开放创作方式；技能中的owned spawn继续使用原共享deployment决策，不误受玩家卡组限制。

同源反例与owned-deployment、scenario效果合计10项通过（3.03秒），CP/完整命令回放相等。生产及c069原字节不改，尚待独立复核和新整体回归。

## 两份内容

`tools/build_chapter01_roster_policy.py` 实际重读12名原生卡片Character Typetree，核对配置/潜能/覆盖，使用冻结角色表的E0L20与原生favorPoint插值，capacity/build/退款参数来自实际Prefab。native deployment-only fixture有真实12卡、费用、57定义和原生容量8；没有普通攻击、所选技能或天赋实现，不能用于完整原生教学战斗验收。

费用的独立预期依原卡顺序为 `16,10,9,8,27,15,13,16,15,7,14,7`。控制场景部署8张最便宜卡成功，总费用83，DP99→16；第9张因capacity拒绝，既有8实例不改，恢复/回放相等。

新固定12人场景明确使用 `fixed12_test_override`，原生12卡完整保存，`native_training_deck_legal=false`。真正消费者是已选定 `scenario.roster` 和新的公开部署成员门；在保留完整原生wave/control/NPC的控制场景中，即使显式给测试DP99，也不能把休眠NPC当玩家卡片重复部署。

| 文件 | SHA |
|---|---|
| m23/level_main_01-11.partial.json |`ac0d293e2679db65e55695a5d8fb6e5e8404b1eba7b485dc45c686d36429ac19`|
| m23/native_card_deployment_fixture.json |`374e06da04f6cf8dd207d91041f61c13b8e751170e03f050fb2fe14d1687d662`|

选择覆盖是目标已明确允许的测试配置，不把它解释为客户端原生合法编队。教学UI/card展示和原生12卡战斗未验证，完整固定12人主线仍待清场、源消费和独立审批；关卡进度保持2/36。
