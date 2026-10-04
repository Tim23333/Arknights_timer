# M18 declared route-checkpoint portal candidate

实现与 wrapper 已冻结为 bounded model candidate，未 promotion、未签 receipt、未执行完整 1-12。M16 669982、f98、primary、旧 partial stage 和 M20 分支未修改。

候选 `D:/Arknights/Arknights_timer/unpack_work/campaign_m18_portal_candidate`，Python implementation digest `283ed55d0aaab3b9d6aaeb4806209182b5b6bb746882d52403ba9ef124a3d999`。由冻结 M16 字节复制，只改 capabilities、spatial_validation、movement、spatial、新 tile_mechanics 和 contracts JSON 六处；完整 diff 与 bytes SHA 在 `validation/campaign/m18_portal/candidate.patch / changed_files.json`。目录路径变化不代替实现身份。

新 source wrapper：`packages/campaign/chapter01_stage_models/m18/level_main_01-12.portal.partial.json`，SHA `6dc89b41ac24e81b0915ebc7dba98250ea3e03a0248dd2ee2af8146d3b1498e9`。builder SHA `412e8c1baf07e81e124824ad3ee3b6af0c6ff2ae99412bfc311d72ea080b8f99`，`--check` 通过。candidate CLI validate 实际 269 definitions / 82 rules，program `98bbb203499aa5fd85fb14fbe160a568dd0336f84e46700c8662a8aa8a3cdd7c`。wrapper 保留 parent partial 的 native tileKey/build/pass/height/source、waves、routes、controls、所有其余定义；只替换 EMP 已审 terrain entity 并声明源 portal profile。精确消费两个旧执行 gap 后仍保留 W/projectile/FSM/完整关卡执行与三维高度等 gap，未清空 pending 自称完整。

## 通用接口

地图字段：

```json
{"tile_mechanics":{"arbitrary_tile_key":{"type":"route_checkpoint_portal","role":"entry","rule":"rule/optional_transition","parameters":{}}}}
```

未知 tile key 必须声明受支持 profile；profile type 仅当前实际实现的 `route_checkpoint_portal`，role 必须 entry 或 exit。type/role/rule/parameters 之外字段拒绝。portal tile 的 blackboard/effects 必须 null 或空 data collection；非空行为与无意义 bool/number/string 不静默忽略。内核没有 `tile_telin/tile_telout` 名称分支。新 wrapper 的两个 key/role 从 exact source audit 的 entry/exit association 推导，原 key 保留。

传送只由源 route 的 DISAPPEAR / WAIT / APPEAR checkpoint 驱动。不选择最近出口、不因一般 actor 走进 portal 格自动 teleport、不添加 actor、kill 或 spawn。profile 没有取代 authored checkpoint 目的位置。

Compiler 对实际可执行 route 的有效 entry/exit 成对验证，使用统一 half-up `project_cell`；静态 reachOffset 使用该 route 明确 axis-sign model 后再投影。未引用 route inventory 不拿来当执行证明。entry 或 exit 只有一方有 portal profile、角色错误、无配对、不同明确 transition rule 均拒绝。单方明确 rule 可控制整对；两方均未声明则用原 route.transition_policy。

Runtime 再检查有效 origin cell/profile、pair checkpoint 与 exit cell。进入时在 World `spatial.portal_capture` 保存 entry 有效 tile/profile、entry/exit checkpoint、entry logical tick 与预期出口。它不放在 movement_path 或本地 cache；terrain revision 清 route path 时不删 capture，CP 恢复保留它。出现前确认 actor 仍在捕获 entry cell/profile；错误出现、外部越格或坏规则输出原子失败。已退场 actor 不继续出现。

公共 `movement.transition` contract 增加可选 `tile_transition` input：当前 origin、destination 的有效 tile/options/profile，以及真实 World capture。默认 pure rule 保持旧 bool/position 决策，允许 expression/graph/provider 按 profile.parameters/capture clock 替换。返回必须遵守 authored hide/relocate/position。getter 的 descriptor/tile/profile 查询纯读，不发 log 或 RNG；真正 transition calculation 与 visibility event 留完整 source/tile/capture 消费 trace。

无 profile 的旧路线不增加 input/payload/capture 字段，保持旧运行语义。隐藏时段、已发 projectile、资源 timer 与 aura 策略仍由原显式 route.transition_policy 决定；本 slice 不重写它们。坐标 relocation 不调用 travel ledger，因此不把 teleport 距离算进沿途 DoT。

## 独立执行范围

`tools/experiments/m18/test_portals.py` 24 个用例，另复制原 M16 的26个独立预期，仅改 candidateRoot 字符串。coherent 共50项，9.47秒全通过；工具逐字校验 copy 等于旧源码唯一 root 替换，旧测试未修改。

新用例包括任意 key 的真实 hide/wait/appear、半开0→3tick、零 teleport ledger、源地图3/35/40秒（90/1050/1200tick）摘录、纯 getter、非自动进入、静态 reachOffset/.49与.5 half-up、World capture 经 terrain 变化及 CP 保留、规则实读 tile参数与 capture tick、entry/exit rule冲突与依赖实际加载、错误profile/BB/effects/配对、runtime origin与规则失败回滚、退场不再appear。另真实 long cast 的任务已进入 cancellation 后，`ability.interrupted` 的纯 recovery freeze rule 报错；完整 checkpoint 恢复 resources、casts、tasks/counters、RNG、事件与 capture。这个 rollback 用例是 API-only，未把直接初始化/手写位置冒称 command replay。其他标注 roundtrip 的真实场景以初态与 recorded commands 完成 replay。

3/35/40 秒用例摘取实际 source portal pair、完整源地图和原 purpose cell，公开 synthetic actor 的零速度只分离 route transition 与其它原生移动行为；excerpt 终点为源出口。它们证明源时钟/位置 consumer，不证明原完整 route 的战斗与原生敌人所有技能。

无 profile 同输入+同命令 M16/M18 对照各170事件。只除原报告中保留的 `runtime_fingerprint / rule_fingerprint` 两个身份字段，所有数值、operands、targets/cause/order/data hash 相等：`1cb312587aa11bf216d635fcce4aa95c133d333ada9b02cdfbc382f77db23ff5`。旧/新身份分别锁定，不重标旧通过。

七个未改 V2 模块205 compatibility项 fresh通过9.65秒。完整 source/helper/actual asset/catalog/preset/core 开始与完成锁由报告记录。

报告 `validation/campaign/m18_portal/candidate_final.json` SHA `2bc187d71d829ba45b49e70b533ea448bf94f233495d0f760c65966bb947161f`；compatibility report SHA `a85b781af62c349134da611951363bbfea2df132ea9db7ddf5944ab01cfd3c91`。新测试 SHA `af34344b0f9166dc34bffcbe039b7859fa1edf7135f59bc29fa9ba5ebc2b7d8a`。

exact source audit 仍为 `65180c96d812a6155144026c42ca54350eb9e03b358c0f3562d9bf348562a339`：四 portal 格、两 generic Tile prefab、8条实际 SPAWN route 的9组配对。native generic Tile/Enemy 方法体、额外 key dispatch、表现与 callback/version/物理参数仍 client_pending；本模型只消费明确声明的 source route profile。完整场景与 fixed12/36目标没有因这批微场景而缩小或获批。
