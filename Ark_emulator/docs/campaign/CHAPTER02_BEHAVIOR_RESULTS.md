# 第2章敌方依赖源闭包与首批内容结果

本批实际目录选择2-9、2-10，完整阶段目标不变。源要求矩阵为 `packages/campaign/chapter02_behavior/requirements.reference.json`，SHA `a5f4c301099a94cc0d6a6477ded8ac9e5be91b9734fec45b39f121f06325b350`。构建工具 `tools/build_chapter02_behavior_requirements.py` 的build/check均通过；矩阵锁25来源文件，保存16个实际variant、原始DB/PPTr/mode/attack/combat/trigger与波次/路线/options。

独立运行根 `../unpack_work/campaign_chapter02_behavior_candidate` 复制冻结M26实现，未改变任何V2源码；其实际digest仍为 `7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe`。M26、primary、旧报告及作者文件未改。只新增source/content builder和公开command probe。

## 冻结的首批7项

`models.partial.json` SHA `bda5488a79f44e195e23631f579d313de833f356f1decec6d6abd726800f9bc8`；`build_chapter02_behavior_models.py --check`通过，原source快照另封存在 `validation/campaign/chapter02_behavior/first7_source`。7passed/3.50s，7个实际运行输入在decode/compile前封bytes/hash/初态/seed2702，63个原资产组件真实Unity Typetree逐项比较，全部source/helper/core前后锁相等。

- yokai FLY + EmptyAnimatedAbility，attack/trigger原生NULL，明确无普通攻击，不落入假physical fallback。实际飞行route10tick移动0.3，无攻击事件。
- yokai_2 FLY但实际MeleeAttack/AdvancedSelector/circle2，使用M25资格和M24声明decision。实际f8伤害：ATK220-DEF100=120；不需要blocker。目标距2.01拒绝，无cast。
- defdrn显式BB圆半径2.5声明模型、DEF additive300，SelfOption2由dump明确EXCLUDE。实际物伤1000-(100+300)=600，离开后900；source自身DEF150未获得自己的光环，实伤850。两个独立source重叠实际300→撤退一源600→再撤退900。没有将原始collider1解释成已证明native2.5。
- skulsr原始PassiveAttachmentAbility减DEF multiplier-.5，fixed5s。使用公开fixture能力施加实际定义，tick149实际物伤950，tick150恢复900。仅验证减防子依赖，不冒称skulsr整套技能/附加时点已闭合。

每个记录command场景均实际CP continuation与完整命令replay相等。报告 `validation/campaign/chapter02_behavior/first7_final.json` SHA `a4a1f83e15d50f27bbe1ff8da82cafbcc35ebc91dd94c8fc3ad11b1a2812b458`。

## 独立的新projectile输出

后续采用新工具 `tools/build_chapter02_projectile_models.py` 与新包 `projectiles.partial.json`，不覆盖first7包/证据。新包SHA `d1b8929579a01d2a3e1cc246eccb5f1a7f05fadd9a2d627b972c27874fca979b`，build/check通过。

Wizard实际RangedAttack f19、arts、ATK200；SimpleProjectile10s/maxHit1/不停止于source-invalid，AdvancedMovement speed10。声明2D homing从launch后下一tick推进：距离2，launch19→hit25，RES20下200×.8=160。Mocock实际f22、physical、ATK180、ParacurveMovement speed5：launch22→hit34，DEF100下80。

新7项passed/3.89s：6个实际运行fixture与1个source/build/full-claim负门，32个敌prefab和弹体组件真实Unity Typetree比较。source23退场不取消已经launch的mocock packet；目标25获得DEF+50后，hit34实际30，体现显式at_hit profile。Wizard目标20移动到距4且source21退场，homing于31实际160。target-free存续时不launch；已launch后目标退场取消，无health allocation。CP continuation和完整recorded-command replay均通过。

报告 `validation/campaign/chapter02_behavior/projectiles_final.json` SHA `cba33edf861342e47959c0263c07e368627f8516e510316e1a761f6b2db8d641`。source stats at_hit和逻辑first-step策略是明确声明profile，原生sampling/FSM/碰撞/高度/动画缩放未取得方法体或客户端证据，不算实际游戏准确。

## 真实尚缺

`require_complete=True`仍拒绝，所有输出 `actual_game_correct=false`、`formal_approved=false`，没有将本批通过升级为整关或native正确。

| 类型 | 具体未闭合项 |
|---|---|
| source_gap | skulsr prefab HpRatioToggleChecker max.40000000596与DB atkup.hp_ratio.5冲突；_loadMinHpRatioFromBlackboard0，不能证明max值的LoadData覆盖算法/源版本对应 |
| source_gap / model_gap | defdrn DB radius2.5与prefab CircleCollider1并存；范围加载算法、SilenceableTalent驱动及TargetValidator全字段adapter尚未消费 |
| model_gap | skulsr近战f53/远程双信号f14/17×.25999999、双mode、攻击附加buff的真实driver尚未拼装；不以独立减防probe替代整套技能 |
| model_gap | aoemag PhysicsRange重叠、原生target mount和capsule相交 consumer未实现；不能用圆/中心点/单体伤害代替 |
| client_pending / source-body gap | Enemy FSM许可/INPUT_TARGET继承、postFilter排序、BB加载、projectile native callback与动画时钟缩放、物理/动态高度方法体未知 |
| witness_missing | 两关完整原生waves/timeline/FLY/routes/runes/control与fixed12 runthrough尚未由本批执行；stage输入/地图/敌人口不能套独立微场景证据 |

Aoemag源几何审计工具 `tools/audit_chapter02_physics_range.py`实际重读两个BoxCollider和各五层Transform父链，并且build/check通过。包 `aoemag.physics.reference.json` SHA `b0b0450156a366780be576995383430304069a6fabab950cf74abfbbd52dab79`：尺寸1×3、3×1，offset0；局部链rotation identity/scale1；root保存prefab场景位置(4,3,0)。原始source PPTr和变换保留，未把这个root摆放当battle地图原点、未作未知nativeAxes投影、未改内核几何。

## 第1章人口与后续ledger

原生1-11的45、1-12的30是waves中SPAWN actions count之和。这些数字不包含预定义NPC/EMP装置或干员owned召唤；source matrix保存原生predefines供区分。已读取敌方serialized组件和五个BSON模板，没有发现有值的非wave创建字段，但原生方法体缺失，不能证明不存在未序列化召唤路径。

后续runthrough应分别记wave敌人、非wave敌人、注册NPC/device、player_owned_tokens。用实际definition/side/ownership/registration/cause分类，wave birth/kill/leak/remaining守恒单独核对；不能把全部World entity births强行与45/30相等。新增源审计/微场景证据没有签正式收据或修改进度。
