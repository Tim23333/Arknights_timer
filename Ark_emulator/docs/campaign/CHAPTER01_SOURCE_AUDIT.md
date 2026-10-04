# 第1章最后两关的原生依赖审计

本批只读取固定36目标中的 `level_main_01-11` 与 `level_main_01-12`，没有修改 core、M6/M7/M8旧包、旧工具或测试。新工具 `tools/build_chapter01_enemy_sources.py` 生成 `packages/campaign/chapter01_sources/` 的 native.reference.json、dependency.matrix.json、attacks.model.json 和 assertions.json。固定公开表 commit 为 `56aee3d6c5a29c3a0d192456d70d14252cbb0804`，native reference manifest 的URL/commit/SHA/size/cache identity、enemy lock 与 operator table lock 都在构建时实际校验；本地Unity/BSON/动画版本另保存来源SHA，不声称与公开表版本一致。外部2025 tokens源另外核对已冻结官方下载证明的SHA/MD5/字节数，版本差异不隐藏。

这是原生来源保留及有限攻击模型，两个关卡均 `runnable=false`，没有整关执行或正式验收证据。

## 原生关卡依赖

| 项目 | 1-11 | 1-12 |
|---|---|---|
| 实际出生次数 | 45，7种敌人 | 30，6种敌人 |
| 控制数量 | STORY2，PREVIEW_CURSOR1，ACTIVATE_PREDEFINED1，DISPLAY3 | STORY1，DISPLAY2 |
| 原生预定义 | 隐藏Adnach1；characterCards12 | trap_002_emp1，LV10，skillIndex0/mainSkillLvl1 |
| 标准难度适用runes | 0 | 0 |
| FOUR_STAR rune源保留 | 3条，未当成标准难度效果 | 3条，未当成标准难度效果 |
| SPAWN引用路线的checkpoint | MOVE46，WAIT_FRAGMENT4 | MOVE186，WAIT_SECONDS12，DISAPPEAR9，APPEAR_AT_POS9 |

两关原始 map/routes/options/predefines/hardPredefines/excludeCharIdList/branches/enemyDbRefs/waves 文档完整保留，来源 SHA 与原始敌DB各level rows/继承后的resolved字段一并保存。排除列表/分支/硬预定义为空仍保留真实 null，未造“已转换”状态。不同关卡同ID若存在不同DB/override，工具严格拒绝合并，要求独立variant身份。

1-11 原生隐藏 Adnach 位于 native row3,col6、RIGHT、PHASE_0 LV20，并在动作 ACTIVATE_PREDEFINED 激活；12张原生卡片与用户固定12 roster是不同来源的依赖，不能静默删除卡片或用E270固定阵容冒充教程预定义配置。这一教程输入策略须下一阶段明确。

1-11 的STORY_a有HEADER/name3/dialog/Blocker，且原生 `blockFragment=true`；STORY_b有PopupDialog5、Delay5（4/4/4/4/2）与不可跳过教程HEADER。它们的原始TextAsset名、字节、base64、payload SHA、每行语法与文本均保留；未套用0-11仅PopupDialog的作者流程，也未猜这些Delay是game time或wall time。

1-12 STORY有HEADER/PopupDialog3/Blocker。所有控制动作原始flags、routeIndex和wave/fragment/action index保存；PREVIEW_CURSOR与ACTIVATE_PREDEFINED尚未转换，不删除，不当成纯emit已完成。

1-11 W使用route2，fragment deadline分别为10/60/120/190秒，并有reachOffset(-.11,+.01)。deadline应使用实际捕获的fragment起点，不能用到达后sleep；M8仅提供这类时间基准的模型能力，原生Scheduler正文仍缺。

1-12 W route2有两对DISAPPEAR/APPEAR，routes3/4/5/6/12/13/14各一对。它们全是SPAWN实际引用，不是未用目录占位。多条路线还带非零reachOffset。当前普通MOVE/WAIT模型不能代表隐身/地下通道/重新出现与offset几何；这些数据保留为明确阻断缺口，不替换成直线MOVE或生命周期死亡。下一阶段需要区分不可选择、停止地面阻挡、保留alive/managed membership、重新定位等模型接口，并单列客户端未证明语义。

## prefab、类名与闭包

工具从exact GameObject递归Transform子树，采集所有挂载Mono，并沿实际本地Mono指针补齐。27个W组件的UnitMode、Talent、ToggleablePassiveBuffAbility、HpRatioToggleChecker、EnemySkill、RangedAttack、SelectorTrigger/AdvancedSelector等均保留原始字段。GameObject层级与mode_index定位可区分两份同名C4，而非把整个CAB其它Boss的Buff扫进此Boss。

类名从序列化的 `m_Script` FileID/PathID追到确切MonoScript CAB读取，保存script源SHA/原始ClassName/Namespace/AssemblyName。这里没有仅凭字段形状给组件猜类名。动画沿本地Animator→renderer→external SkeletonDataAsset→TextAsset解析，保存exact Spine原始payload/hash与真实动画绑定；私有BE reader身份锁定，旧共享库未修改。

原生BSON模板保存每个所需子文档原始base64/SHA与解析结果，当前缺失模板0；包括W mode-switch以及预定义单位所需空模板、先锋天赋等。相关 dump.cs 的 HpRatioToggleChecker/EnemySkill/RangedAttack/MultiMeleeAttack/SimpleProjectile/ParacurveMovement/AttachToTarget/AbstractAnimatedAbility 声明及TimeMode枚举保存，方法体均为空，不能当成实际客户端算法。

## W：确证与缺口

W两关都是level0、HP10000/ATK470/DEF100/RES50、rangeRadius2.5、mass5、lifePointReduce2。它有两个UnitMode：Default0与T1=1。

HpRatioToggleChecker实际 `_minHpRatio=0,_maxHpRatio=.5,_useLTForMax=0,_toggleOnce=0,_restoreDelay=0`。Buff `cqbw_t_1` 没有属性修改列表，BB为mode1，template为switch_mode_restart_fsm。BSON ON_BUFF_START读BB mode并restartFSM；ON_BUFF_FINISH恢复default并restartFSM。不能凭名字AtkUp造ATK加成，也不能把toggleOnce0写成不可逆阶段。比较边界、持续与治愈后恢复的原生正文未恢复；这些是字段支持的可替换模型方向，非已实现Boss。

两个mode普通攻击都是RangedAttack、physical1、raw atkScale1、projectile_enemy_cqbw；真实Attack动画有OnAttack9与23，不能复制首章单次近战。正常弹道SimpleProjectile maxHit1/lifetime10、ParacurveMovement speed5；跟踪、弧线距离、碰撞、失效与回调时序保持pending，未将视觉爆炸效果当成已证明AOE半径。

DB C4：priority5、initCooldown9、cooldown20、spCost0、BB atk_scale1.8/range_radius2.5。Default与T1各有确切C4 EnemySkill和RangedAttack：Default init override−1、selector为空；T1 init override0、显式SecondaryFilterAdvancedSelector maxNum3。共同raw preDelay0.6000000238418579、waitForAttackEvent0、timeMode1（FROM_ANIMATION）、waitForProjectileInvalid1。这不能直接当成固定0.6秒客户端发包公式，因为AbstractAnimatedAbility.GetTimeScale等正文缺失。

C4 projectile_enemy_cqbw_s1 是SimpleProjectile + AttachToTarget，lifetime3.200000047683716、alwaysHitTraceTargetInTheEnd1、stopAfterMaxHit0，visual effect onReach/targetStart分别保留。其真实“何时引爆/失效/是否目标死亡后仍伤害/施放冻结”需要回调与FSM接口；没有用普通projectile speed5代表它，也没有仅按技能文字造AOE。

## 可运行的普通攻击子集

这里只作者exact单模式MeleeAttack、无原生passive/activeBuff或技能依赖的六种敌人，使用源 `_atkScale/_damageType` 与exact OnAttack帧。角色/关卡ID没有进入通用内核。

| native ID | ATK | Source帧 | synthetic DEF30、HP2000后的独立期望 |
|---|---:|---:|---:|
| enemy_1000_gopro | 190 | 18 | 1840 |
| enemy_1000_gopro_2 | 260 | 18 | 1770 |
| enemy_1002_nsabr | 200 | 12 | 1830 |
| enemy_1027_mob | 250 | 12 | 1780 |
| enemy_1029_shdsbr | 240 | 12 | 1790 |
| enemy_1030_wteeth | 500 | 19 | 1530 |

CLI实际Engine验证六项：前一tick HP不变，源frame tick后仅真实blocked target受物理损失，另一同格player保持2000。内容Compiler61 definitions/41 rules。完整program/runtime fingerprints、implementation digest与源产物SHA保存在assertions.json。Defender为明确合成fixture；这是未缩放source-event模型的验证，不是客户端攻速/动画FSM校准，也没有运行整关。

`enemy_1014_rogue` 的确切类是MultiMeleeAttack，源additionalTimes1、waitAttackEventForAllAttacks1、splitDamage1、OnAttack12/23；已从简单子集排除，不能将两个事件都按ATK350全额伤害。分伤公式及回调计数保留pending。`enemy_1028_mocock` 和 `_2` 都是RangedAttack、OnAttack22、projectile_mocock（speed5），虽然源已取得，目标/追踪/impact尚未转换。Boss同样不会获得一条假“普通近战已完成”能力。

## EMP与预定义来源

十三份1-11预定义角色charpack子树和确切表子集均保存，但不作E0LV20等配置的运行转换声明。1-12 EMP raw字符表/skill表、sktok_emp技能CAB都取本地/固定pin来源。EMP trap本体来自已校验官方2025-03-27 tokens AB；该版本差异显式记录，不冒充2026-09-29客户端源。

EMP skill level1为MANUAL，SP5/init0，BBcost10、stun7、rangeId x-4；本地MeleeAttack实际timeMode2（SPECIFIED）、preDelay.75、cooldown1.5、arts2、raw atkScale1、on-hit stun Buff的durationKey=stun。Trap是MapDependentTrap/TrapMode，保留tile buildability/passable/height rewrite与passive abnormalFlags，不当成普通floor。没有宣称已转换伤害属性、一次性销毁、费用、交互及地图覆盖生命周期。

## 复现与边界

运行 `..\.venv\Scripts\python.exe tools/build_chapter01_enemy_sources.py` 生成新产物；`--check` 重读所有原始输入并检查源、helper、BSON、动画、产物及实际模型断言。没有新增pytest文件，不触发当前全tests收集变化，未修改正在执行的core身份。

依赖矩阵可供root下一阶段按真实scope组合。两关的未知checkpoint、tutorial controls/predefines、Boss、分伤与ranged/impact仍是实际缺口；不能将六种攻击模型或“所有源可读”提升成36关正式通过。
