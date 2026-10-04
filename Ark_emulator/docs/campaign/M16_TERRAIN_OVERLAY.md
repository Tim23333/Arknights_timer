# M16 owned terrain candidate

本页是候选实现与局部模型证据，未签批准收据，未合入 primary，也不表示完整 EMP 或第一章通过。冻结父版本 f98、旧 EMP category 79ed、旧证据与生产代码均未改。

候选目录：`D:/Arknights/Arknights_timer/unpack_work/campaign_m16_terrain_candidate`。最终 Python implementation digest 为 `669982006a81507973d8f3c3abb1f694d7ee9831de67ad2de1c0b3ea441df571`。规则 catalog 与 preset JSON 另由 coherent report 开始/完成 hash 锁定，不能只用 Python digest 代替全部规则身份。

新 EMP wrapper 是 `packages/campaign/chapter01_devices/emp.terrain.json`，SHA `362c2fb4a102197ff23b6ff48379c8940a98127bbfb6848b6ab4e837f673edb2`。builder SHA `aeb22c3ab7f0c3a42e960c83eccbf71420ea3450232a7b43fe4d4538763df51a`；独立保留 base category package 的 SHA、原 source reference SHA 与两份实际 Asset bytes SHA。`--check` 通过。候选 CLI validate 通过，实际闭包 52 definitions / 43 rules，program `073304ad793e91f22666cb3483d3cf937a41faa7ac02e489aabecbb0d1a17466`。

## 接口与状态

实体 `components.terrain_overlays` 是列表；每层显式 `{key, priority, values, preserve?, rule?}`。出生时绑定 actor 的整数 cell。它是固定 cell 的层；以后移动 actor 不暗中搬层。效果 `apply_terrain_overlay` 使用同规格 `parameters`，可显式加整数 `position`，否则采用所选 owner 当前位置。`remove_terrain_overlay` 必须声明 `parameters.key`，只清所选 owner/key。生命周期内部按 owner 清所有层；battle 不能拥有层。control/scheduled battle effect 必须选 actor 或给明确 actor ID，不能因带 selector 就把 `source` 指到系统 battle。

World 中 `system/battle.components.state.terrain` 保存 `next_id / revision / layers / effective_tiles`。同 owner/key 是替换：旧层删除、新 monotonic sequence 分配；其他 owner/key 不变。默认 pure provider 按 priority 从小到大、再 sequence/owner 排序合并，较后层仅覆盖它声明的字段。priority/顺序是明确数学模型，原生 TrapMode 方法体未恢复。重叠层若给不同显式 tile rule 会拒绝，不偷偷选择一个。

可写字段为 `buildableType / passableMask / heightType / physicalHeight / advancedBuildMask / obstacleLikeMoveCost`。严格拒绝未知字段、非整数 mask/priority、bool-as-mask、非有限高度、未知 preserve、重复 preserve、preserve 与 values 冲突、地图外或非整数 cell。初态/波次/template 的 overlay 与 explicit effect position 都经过 compiler preflight；不能保证整数 cell 的随机 owner placement 被明确拒绝。公开 effect 中的 `parameters.rule` 是专门的依赖引用，闭包会实际加载它。

`terrain.tile_options` contract 输入 base、layers 与 position，输出 tile data；默认 provider `ark.terrain.tile_options` 可由 scenario binding 或明确 rule 替换。getter 只调用 `rules.evaluate`，不发 calculation/event，不消费 RNG，不改 World/tasks。变化才写 World 并发 `terrain.changed`，记录有效 tile、rule 与完整 trace。时间/custom-rule 输出改变由 phase 0 同步检测。不存在跨恢复持有的 effective-map cache。

## 消费者与源字段

EMP TrapMode 的实际 raw options 是 buildable0 / pass2 / heightType0 / advanced0 / overrideObstacleLikeMoveCost1；四 rewrite/keep 字段逐个严格核对 int 0/1。keepCurrentPassable=1、rewriteHeightType=0、rewriteAdvanced=0 因而保留当前 pass、heightType、advanced；不能把 source options 的 pass2 当作已执行的覆盖。rewriteHeight=1 则执行 source `.4000000059604645` 的 numeric physicalHeight。MapDependentTrap rewriteTileOptions1、occupiedCnt0、withdrawable1 保留，并沿用容量0和公开撤退行为；advancedBuildableMask1 变成显式 deployable required mask1。

| 有效数据 | 当前实际消费者 | 范围边界 |
|---|---|---|
| buildableType | deployment.eligibility | EMP birth 后 cell 禁止部署，owner 退场恢复原值 |
| passableMask / groundPassable | GridTopology.path / passable / clip_segment，与纯 movement.path 的 effective map 相同 | 写 mask 实际切断已缓存路线；清层后重建并继续。FLY 仍按原 motion 模型 |
| advancedBuildMask | 显式 deployable.parameters.advanced_build_mask 的 eligibility | 缺失 tile 值使用声明模型 DEFAULT1；没有显式 required mask 的旧部署不新增拒绝 |
| heightType | effective tile / deploy.eligibility 输入 | EMP 保留已有值；没有假装改成高台或提供 native height physics |
| physicalHeight | effective tile 与可替换 deploy.eligibility 输入 | numeric `.4` 有真实数据接口；当前二维碰撞不利用三维高度，仍 model_gap |
| obstacleLikeMoveCost | movementCost 的加权最短路径 | 默认 normal1 / obstacle3；实际 numeric path consumer 与 replaceable rule 测试通过。原生权重未知，client_pending |

层增删/动态变化先清 route actor 的 movement_path、velocity、wait revision，再同步阻挡。新 mask 使路线不可达时 actor 在该 revision 等待，未吞掉其他规则错误；下一次层变化使其重算。owner retire/death/withdraw 在 Buff/aura reconcile 和 owned-child cleanup 之前先清本 owner 层；outer transaction 回滚 World、层计数、任务、RNG、事件与路径状态。派生 grid 没有旧 overlay cache，恢复后直接读恢复后的 World。

## 实测与证据

- `tools/experiments/m16/test_terrain.py`：26 项，3.73 秒，全部通过。覆盖 birth/pure getters、部署拒绝与撤退恢复、保留 pass/height/advanced、重叠 priority 与稳定 sequence、替换/只清 owner、实际加权路径、自定义规则、已有 route 同步失效与阻断/恢复、时间规则、CP restore、recorded-command replay、death/owned child/task cleanup、effect 与退场失败完整回滚、control actor selector、坏字段/位置/上下文与坏 rule 输出。
- 新身份下复用原 EMP 六组实际行为回归通过，包含 packet .75→tick23、packet 前再选、800 arts、半开 stun、三 damage types 无敌、SP/DP 拒绝、空目标/退场/idempotency、owned jobs/rollback 与 battle 禁用；复用测试边界仍属于模型，不转成 native 方法体证据。
- 七个未改 V2 模块 205 项兼容通过，9.57 秒。第一遍 204+1 的失败是独立 runner 未把 repo tools 加入 import path；第二遍起已修 runner，未修改旧测试或 runtime 以回避预期。
- f98 与最终候选使用字节相同的无 overlay category 场景，分别 286 events。只排除保留在原 report 中的 `runtime_fingerprint / rule_fingerprint` 两字段，全部数值、operands、source/targets、cause、顺序和其他数据的规范哈希相等：`17c8a006e8e08d296d382b9788f98da3a75794670f9e4b55137d497e315986a3`。两边 terrain 均未加载，无额外 terrain events。program/runtime 身份变化明确保留，不冒称旧指纹。

coherent report：`validation/campaign/m16_terrain/candidate_final.json`，SHA `658cbcfcd66771c102df643f9e8e0f8d32a3c9ab0c2596395f35385ec323eee3`；每个已创建 fixture 留初态、recorded commands、实际 World/event，测试源码及 raw assets 开始/完成一致。API-only rollback/getter 与 compile negative 不冒称 command replay。兼容 report：`compatibility_final.json`，SHA `20010de3d3358bae7c522925b3209e5b338dca57afdcf79868ed0cc320d645d5`。`candidate.patch / changed_files.json` 给 parent 独立核对全部候选差异。

最终仍保留 source/client gaps：原生 TrapMode 合并优先级和 movement cost 权重方法体、二维之外 physical height、2025 token bundle 与2026来源对应、CastSkill callback 时钟，以及 chapter 场景 dormant/card 约束。这个 slice 没有删除这些边界，也没有 promotion 或全关验收收据。

## Root 独立补充复核

Root 未复用作者的 fixture 或 helper，另写 `tools/experiments/m16_root_peer/test_terrain_review.py`，3 项实际通过（0.63 秒）：
同 key 两个 owner 的层，退场只清一个 owner、实际 walker 恢复及 CP/命令回放全部事件相等；
仅在 overlay 中引用的规则加载、非法 movementCost 的整个 checkpoint 回滚；
真实 EMP wrapper 保留 pass3 / advanced0 / HIGHLAND，纯读取不改变 checkpoint，撤退恢复完整原 tile。
初次测试误用 `cast` 命令并漏写 EMP 的 battle DP 资源，两个 fixture 失败原报告保留；修正后未修改候选。

报告 `validation/campaign/m16_terrain/root_peer_review_20261002.json` SHA
`a710e69ff1633a508b2274296e21cc3f6aaa48e9a05e9076c13c42963ccc8aa0`。
测试前后候选 core 相等；测试源码与包装源是运行后绑定，没有冒称 in-process 开始源码捕获。
这是独立局部检查，catalog 子 agent 的进一步复核仍待进行，也不替代完整关卡收据。
