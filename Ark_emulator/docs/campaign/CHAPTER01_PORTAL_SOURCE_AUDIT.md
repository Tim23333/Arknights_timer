# 1-12 portal tile source audit

只读源审计，不是运行通过、native 方法体恢复或收据。M16 候选及 primary 均未因本审计修改。当前 validator 对未知 portal mechanics 的拒绝应继续保留，直到新内容显式绑定已审查的模型。

`tools/audit_chapter01_portal_tiles.py` 保存 exact source/PPtr/MonoScript 与完整路线依赖到 `validation/campaign/chapter01_portal_source_audit.json`；重复 `--check` 通过，artifact SHA `65180c96d812a6155144026c42ca54350eb9e03b358c0f3562d9bf348562a339`。母 source reference 仍为 `a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd`。

四格来自 `mapData.tiles` index 14/68/71/75，均 LOWLAND / NONE build / ALL pass / ALL player side、blackboard=null、effects=null。matrix row 与 native route row 是相反方向；不能直接拿 route row 索引 matrix：

| Palette index / key | Matrix position | Native route position |
|---|---|---|
|14 / tile_telout |(6,3)|(1,3)|
|68 / tile_telin |(1,2)|(6,2)|
|71 / tile_telout |(1,5)|(6,5)|
|75 / tile_telin |(1,9)|(6,9)|

精确 tiles asset `data/battle/prefabs/[uc]tiles.ab_unpacked/CAB-a3035ec54e4c62f1271965a646b6fe4e` 的 GameObject `tile_telin` 与 `tile_telout` 分别 PathID `-1118782109054650377`、`6415330578311357900`。每个都有 Transform 和一个 MonoBehaviour，其外部 MonoScript PPtr 精确解析为通用 `Tile` class（m_FileID1 / m_PathID8835298718773198526）。Serialized objects 没有专用 teleport component、入口出口配对字段或额外 effect/graphic 子对象。reference 封存其实际 component bytes 解码数据、script CAB/source hash；并没有根据名字猜 class。

实际 SPAWN 使用 route 2、3、4、5、6、12、13、14；这些 route 共九组 DISAPPEAR→WAIT_FOR_SECONDS→APPEAR_AT_POS。每个 DISAPPEAR 前最近 MOVE 的名义 cell 均是 tile_telin；每个 APPEAR 的明确目的 cell 均是 tile_telout。八条 route 全部确实被 source waves 使用，未拿 placeholder 路线证明流闭包。hidden waits 为 3/35/40 秒；route2 的两次传送分别使用35与40秒，不是通用固定三秒。

最小通用内容策略建议：显式 `route_driven_portal` tile mechanic profile，保留原 tileKey/build/pass/options；该 profile 只声明本地图 tile 身份与已有 route checkpoint 的关联。隐藏、等待、重定位仍由原 DISAPPEAR/WAIT/APPEAR 执行；不从距离自动配对出口、不因一般 actor 走进某格就新增 teleport effect、不创建 shadow actor，也不改变原路线时钟。需要保留 source checkpoint/格关联证明，非空 blackboard/effects 或未知 profile 明确拒绝。可替换 tile profile 名称和匹配规则应为内容声明，不能是 official tile ID 的硬编码角色分支。

实现前独立预期：3/35/40 秒各一条 source route 的隐藏半开时段与显式目的位置；同 tick 隐藏从 blocking/targeting 移除、出现后重新加入；teleport 不产生 combat.kill/spawn，也不能算移动路径距离触发沿途伤害；源 actor 退场清理待执行任务；CP 与只用 recorded commands 的 replay；入口/出口指向错误、未配对、非空 tile blackboard/effects 负例。另保留一条一般 actor 走过 portal cell 的非自动跳转模型边界，不将它冒称客户端行为。

两 prefab 都是通用 Tile 且无额外序列化算法，不足以证明 native Tile/Enemy 方法体没有按 tile key 分支。方法体、表现特效和客户端 comparator 仍 client_pending。现有 hidden/appear 原语可表达该明确数学策略，但本审计没有替新 stage package 宣称已消费或已执行。
