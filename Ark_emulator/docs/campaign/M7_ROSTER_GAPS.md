# M7 我方行为缺口审计

2026-10-02。只新增本报告、`tools/build_m7_roster_profiles.py` 与 `packages/campaign/roster.profiles.json`；M6工具、内容、测试和证据未修改。使用真实V2 Compiler/Engine读取冻结内容建立运行见证。原生声明、当前模型、建议profile与客户端证据分开记录；本轮无formal approval，正式关卡仍0/36。

## 1. 凯尔希普通治疗：字段64不能直接映射为36

实际 charpack/attacks.reference 中的唯一普通治疗selector具有 `_postFilter=64`、`_maxNum=1`、`_includeOwner=1`、`_ignoreHealFree=0`。dump.cs中精确对应：

- `FilterUtil.FilterType.KALSIT_M3_SELECTOR = 64`，声明位于 dump.cs:435580。
- `HP_RATIO_NOT_FULL_ASC_MY_TOKEN_OR_ME_FIRST = 36`，声明位于 dump.cs:435552。
- `_Filter_KALSIT_M3_SELECTOR(Entity candidate, Entity source, out FP weight, out FP priorWeight)` 位于 dump.cs:436071，只有 `{ }` 空方法体，不能据方法名补算法。

枚举64包含M3命名，固定配置却无模组。不能因此自动套模组，也不能把64重标成36。官方固定配置第一天赋文字明确优先自身与Mon3tr，可作为无装备语义模型依据；当前版本字段64的原生分支、排序次键和模组检测仍需要方法体或客户端见证。新artifact封存确切selector、整个枚举声明及方法stub身份。

实际冻结编队模型使用普通最低HP率，三个真实输入均选中属于另一医师的Mon3tr：

| 输入 | 当前冻结内容选中 | 新明示profile的独立预期与实际结果 |
|---|---|---|
| 自身60%、自有Mon80%、普通友军10%、他人Mon5% | 他人Mon5% | 自身60% |
| 自身满血、自有Mon80%、普通友军10%、他人Mon5% | 他人Mon5% | 自有Mon80% |
| 自身及自有Mon均满血、普通友军10%、他人Mon5% | 他人Mon5% | 回退选他人Mon5% |

新 `rule/m7_kalts_noequip_own_or_self` 已实际编译并通过这三条断言。它按源UID/所有权与内容参数中的精确Mon定义分类：可治疗的自身/自有Mon优先，组内最低HP率，其他对象回退最低HP率。HP满、死亡、HEALFREE、超出范围仍由现有治疗筛选负责。这是 `explicit_noequip_semantic_model_profile`，`native_enum_64_method_verified=false`，不声称还原64方法正文。

最小通用接口：可现有纯 `targeting.score` 规则实现优先类别，再通过内容参数绑定“preferred_owned_definition”；更通用的实现应把 `targeting.preference` 的类别与score做稳定的字典序比较，而不是每个角色在内核写ID。治疗预期还应覆盖自身满血、自有Mon死亡/离开范围、他人的同类Mon、自有其它召唤物、HEALFREE、同组HP率相等及UID稳定次序。priority只影响可治疗集合，不应产生一次给满血或免疫目标的无效治疗来丢掉其它伤员。

## 2. 夜莺幻影：只找到HP耗尽时钟，未证明额外硬寿命

已检查官方外部2025聚合bundle的default `token_10003_cgbird_bird` 完整语义引用闭包。其root MonoScript是 `Torappu.Battle.Character`，不是水炮/Mon3tr的 `Token` 类型。root `_occupiedRemainingCharacterCnt=0`，模式attack和attackTrigger都是空指针；不能给它填普通攻击。

当前检查到的root字段没有 `_lifeTime`、`_isInfinity`、`_cardPolicy`、`_rechargeOnlyOnce`。不能拿另一个Token的这些字段解释幻影；“没有序列化字段”也不能证明原生Character方法没有隐藏寿命逻辑。相关方法体未取得，artifact明示 `fixed_expiry_native_method_verified=false`。

确定来源是token自身E2/pot1黑板 `hp_ratio=.03`，实际buff `bird_t_1[drop]` 的 `triggerInterval=1`，BSON `periodic_damage_by_hp_ratio[skip_modifier_fix]` 执行PURE `DamageViaMaxHpRatio`，`_ignoreForSp=true`、`_skipModifierEvent=true`。HEALFREE为另一个源buff的abnormalFlags[7]。现有明示模型只有每秒3%有效maxHP自损，HP耗尽时经lifecycle死亡，不自动另设30秒/35秒expire。

无其它改变时，满血幻影连续34次3%脉冲会耗尽；这只是已知HP模型的算术结果，不是原生固定34秒寿命。受到伤害会提前死亡；允许的再生、maxHP变化或其它来源可能延长时间。若后续证据证明另有硬时限，必须增加独立的life/expire机制，不能通过修改HP tick伪造。

建议独立预期：出生后第一个1秒脉冲、33次与34次边界、真实敌伤死亡、owner撤退清理、普通heal拒绝、明确允许的regenerate作用，以及受控抵消自损后是否仍被硬expire。后者在取得native证据前应标model-only测试，不是客户端寿命通过。

### 卡片回补来源与当前模型边界

BSON `charge_token[born]` 的 `ON_OWNER_BORN` 调用 `RechargeToken`：`_cntKey='cnt'`、`_rechargeTiming='NORMAL'`、`_refreshRemainingCnt=false`。固定夜莺天赋cnt2，token表 `max_deploy_count=2`；dump中的 `Nodes.RechargeToken.Execute(...)` 仍是空stub。原始图证明回补监听的是owner born，不证明召唤物死亡/撤退就回补，也未证明add、reset、clamp算法和同owner卡池冷却方式。

M6模型source bird_cards初始2、每次扣1、DP5同原子事务；两张卡耗尽后不因幻影死亡自动补1。幻影cooldown20是源表redeployTime，owner-scoped history与出生回补的原生交互仍pending。新profile将这些条件显式记录，没有擅自把 `_refreshRemainingCnt=false` 改成每次刷新到2。

最小通用接口：owner-birth deck/resource action、声明式card-pool身份及回补策略（add/reset/clamp必须显式）、owner-scoped cooldown/history和原子spawn付款。不应把角色ID写入内核。独立预期包括第一次出生、连续两次spawn、第三次拒绝且DP不扣、幻影死/退时不未经声明回补、owner退/重新出生、出生前剩余卡非0、同时两个实例的共享冷却、卡数满时回补是否溢出。这些策略需分别标native证据和model profile。

## 3. 能天使maxHP祝福：当前HP策略不能由属性倍率猜出

实际charpack/当前talent包确认ATK+6%、maxHP+10%的属性modifier，friend来源在source退场时移除。没有原生方法体证明当前HP是保持绝对值、保持比例、保持损失量，或仅出场时补满。M6包明确birth/callback alignment pending，因此不能把一种直觉算法写成已经验证的游戏公式。

初次只读实际复现曾发现一个与native算法选择无关的模型不变量漏洞：

| 步骤 | 修复前实际结果 |
|---|---|
| buddy1000/1000获祝福 | 1000/1100 |
| 祝福期间HP调整到1050，然后移除 | 1050/1000，超过有效容量 |
| 接着一包true1伤害 | 变成1000/1000，`damage.accepted.amount=50` |

root在本轮审计后添加通用capacity-change处理。新builder当前fresh见证：移除后直接1000/1000，之后true1变999/1000、事件amount1。修复前结果在artifact单独标历史只读观察，未冒充当前回放。

当前出生与增益仍是保持绝对HP：Exu自身初始1598、有效maxHP1757.8；满血buddy1000获友方祝福后为1000/1100。这是模型行为，不能因最大HP数值正确便把出生当前HP判为native校准。

建议接口为可替换 `resource.capacity_change` 或health policy：输入old_current/old_capacity/new_capacity、出生或buff变化原因、source/target以及明确策略；输出新的current和独立事件。至少在apply/remove/expire/refresh/aura离开、source退场与reversible checkpoint中保持 `0 <= current <= effective_capacity`，capacity同步不要伪装成治疗攻击，也不应触发Saria返SP。

四种profile应分别声明：

| 策略 | 旧500/1000变新cap1100的预期 | 证据状态 |
|---|---:|---|
| preserve_absolute_clamped | 500 | 当前模型采用绝对值，移除夹界已补；native未证实 |
| preserve_ratio | 550 | 可选model profile，native未证实 |
| preserve_missing_hp | 600 | 可选model profile，native未证实 |
| initialize_full_on_birth | 仅显式满血出生时1100 | 与既存伤员的buff行为分开，native未证实 |

关键独立预期：满血与伤员获buff、buff下HP高于基础上限时移除、source退场自动移除、Buff半开expiry、多个HP增益、初始buff后的actor birth、场景显式伤残出生不能被自动补满、移除后下一1伤害确实只记1，以及checkpoint/回放。出生policy与运行中的capacity policy不能混为一项。

## 产物与可重复验证

```powershell
..\.venv\Scripts\python.exe tools/build_m7_roster_profiles.py
..\.venv\Scripts\python.exe tools/build_m7_roster_profiles.py --check
```

工具只写新profile包，重建完整来源hash、enum/方法声明、冻结内容输入身份与当前运行文件hash；执行Kalts原模型/新profile六个真实selector场景，并用当前V2执行HP变更及真实1伤害见证。profile的三个分类预期是独立assert，不仅把当前结果抄到metadata。当前 `--check` 通过；root修改M7实现/输入后需重新封身份，M6历史证据不会自动升级。

### 方向转换补充审计

root发现M6selected skill的部分native grid-offset selector仍设 `rotate_with_facing=false`。新builder沿实际 `ability/campaign_angel_normal.selector` 取定义，设置caster同一个中心，分别放左右近1格、native正列最大距离边界、边界外1格的真实候选。旧False配置下left/right两种部署都选右侧近/边界；新True配置下left只选左侧近/边界，right只选右侧近/边界，外1格均排除。这四个实际Compiler/selector见证已冻结进 `direction_grid_witness`，True场景对独立几何预期作assert。不能用fixture固定right朝向证明正式部署方向正确；circle/all不适用该变换。

M6历史pending文字 `Weedy_cannon_default_source_recovered_normal_runtime_conversion_pending` 已过时：默认normal自动包和f1发射→f4落地已有实际通过；后续应细化为external2025/local2026吻合、native begin/loop回调与客户端时钟/采样对齐。按冻结要求本轮不改M6包和工具，在此单列，下一阶段随身份更新修正文案。

当前0-10首关长脚本实际使用Myrtle/Bagpipe/Exu/Ptilopsis/Eyja/Saria，固定12人deck保持。Kalts优先级属于全12能力完整性缺口；Exu当前HP直接影响本脚本生存。spawn jitter/diagonal/steering等关卡缺口是独立审计范围，不能因我方profile已运行就把正式36关或全部native模块标通过。
